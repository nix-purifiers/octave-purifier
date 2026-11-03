"""Scoped native package capture and frozen package-manager activation."""

from pathlib import Path
import sys

root = Path(sys.argv[1])


def patch(name, old, new):
    path = root / name
    text = path.read_text()
    assert old in text, (name, old)
    path.write_text(text.replace(old, new))


patch(
    "pkg.m",
    "  ## If user is superuser",
    """  if (! isempty (getenv ("OCTAVE_PURIFIER_FROZEN")))
    prefix = archprefix = getenv ("OCTAVE_PURIFIER_PREFIX");
    user_prefix = true;
    local_list = getenv ("OCTAVE_PURIFIER_LOCAL_LIST");
    global_list = getenv ("OCTAVE_PURIFIER_GLOBAL_LIST");
  endif

  ## If user is superuser""",
)

patch(
    "pkg.m",
    "          file = char (file);  # convert cell to char string",
    "          file = char (file);  # convert cell to char string\n          url = file;",
)
patch("pkg.m", "isfile (file)", "(isfile (file) || isfolder (file))")

patch(
    "pkg.m",
    '    case "install"',
    """    case "install"
      if (! isempty (getenv ("OCTAVE_PURIFIER_FROZEN")))
        locked = jsondecode (fileread (getenv ("OCTAVE_PURIFIER_MANIFEST")));
        all_locked = ! isempty (files) && ! isempty (locked.nodes);
        for k = 1:numel (files)
          if (! isempty (locked.nodes))
            all_locked &= any (strcmp ({locked.nodes.name}, files{k}));
          endif
        endfor
        if (all_locked)
          printf ("Using locked Nix-resolved packages\\n");
          return;
        endif
        for k = 1:numel (files)
          selected = canonicalize_file_name (files{k});
          allowed = canonicalize_file_name (getenv ("OCTAVE_PURIFIER_PROJECT"));
          if (isempty (selected) || ! strcmp (selected, allowed))
            error ("octave-purifier: package absent from lock; update the lock");
          endif
          files{k} = getenv ("OCTAVE_PURIFIER_PROJECT_ARCHIVE");
        endfor
      endif""",
)

patch(
    "pkg.m",
    "  switch (action)",
    """  if (! isempty (getenv ("OCTAVE_PURIFIER_FROZEN")))
    if (any (strcmp (action, {"update", "uninstall", "rebuild"})))
      error ("octave-purifier: change selection with octave-purifier lock --update");
    endif
    if (! isempty (files) && any (strcmp (action, {"prefix", "local_list", "global_list"})))
      error ("octave-purifier: locked package paths cannot be replaced");
    endif
  endif
  switch (action)""",
)

patch(
    "pkg.m",
    "        ## make sure the PREFIX",
    """        if (! isempty (getenv ("OCTAVE_PURIFIER_CAPTURE")))
          fid = fopen (fullfile (getenv ("OCTAVE_PURIFIER_CAPTURE"), "selected.json"), "w");
          fputs (fid, jsonencode (files)); fclose (fid);
          retained = {};
          for k = 1:numel (files)
            target = fullfile (getenv ("OCTAVE_PURIFIER_CAPTURE"), sprintf ("archive-%d.tar.gz", k));
            if (isfile (files{k}))
              copyfile (files{k}, target);
              retained{end+1} = target;
            else
              retained{end+1} = files{k};
            endif
          endfor
          fid = fopen (fullfile (getenv ("OCTAVE_PURIFIER_CAPTURE"), "archives.json"), "w");
          fputs (fid, jsonencode (retained)); fclose (fid);
        endif

        ## make sure the PREFIX""",
)

# Preserve the URL selected by the native index lookup, before temporary cleanup.
patch(
    "pkg.m",
    "            files(strcmp (files, file)) = {tmp_file};",
    """            files(strcmp (files, file)) = {tmp_file};
            if (! isempty (getenv ("OCTAVE_PURIFIER_CAPTURE")))
              origin = file;
              if (exist ("url", "var"))
                origin = url;
              endif
              fid = fopen (fullfile (getenv ("OCTAVE_PURIFIER_CAPTURE"), "origins.jsonl"), "a");
              fputs (fid, [jsonencode(struct("archive", tmp_file, "url", origin)), "\\n"]);
              fclose (fid);
            endif""",
)

patch(
    "private/install.m",
    "  ## Prepare each package for installation.",
    """  if (! isempty (getenv ("OCTAVE_PURIFIER_CAPTURE")))
    for k = 1:numel (descriptions)
      descriptions{k} = rmfield (descriptions{k}, {"dir", "archprefix"});
    endfor
    fid = fopen (fullfile (getenv ("OCTAVE_PURIFIER_CAPTURE"), "metadata.json"), "w");
    fputs (fid, jsonencode (descriptions)); fclose (fid);
    for k = 1:numel (tmpdirs)
      rmdir (tmpdirs{k}, "s");
    endfor
    return;
  endif

  ## Prepare each package for installation.""",
)

patch(
    "private/install.m",
    "        desc = get_description (filename);",
    """        desc = get_description (filename);
        if (! isempty (getenv ("OCTAVE_PURIFIER_FROZEN")))
          frozen = jsondecode (fileread (getenv ("OCTAVE_PURIFIER_MANIFEST")));
          if (! isequal (jsondecode (jsonencode (desc)), frozen.project))
            error ("octave-purifier: project metadata differs from lock");
          endif
        endif""",
)

patch(
    "private/get_validated_pkg_list.m",
    "  ## The __pkg__ struct",
    """  if (! isempty (getenv ("OCTAVE_PURIFIER_FROZEN")))
    error ("octave-purifier: registry refresh is disabled; update the lock");
  endif

  ## The __pkg__ struct""",
)

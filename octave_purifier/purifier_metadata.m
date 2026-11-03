function result = purifier_metadata (source)
  temporary = "";
  unwind_protect
    if (isfolder (source))
      directory = source;
    else
      temporary = tempname ();
      mkdir (temporary);
      files = unpack (source, temporary);
      matches = files(! cellfun ("isempty", regexp (files, "(^|/)DESCRIPTION$")));
      [~, index] = min (cellfun (@numel, matches));
      directory = fileparts (fullfile (temporary, matches{index}));
    endif
    result = get_description (fullfile (directory, "DESCRIPTION"));
  unwind_protect_cleanup
    if (! isempty (temporary))
      rmdir (temporary, "s");
    endif
  end_unwind_protect
endfunction

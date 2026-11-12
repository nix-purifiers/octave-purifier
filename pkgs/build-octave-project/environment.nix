{
  lib,
  octave,
  nativePkg,
  purifier,
  runCommand,
  fetchurl,
  python3,
  writeText,
  sdkVersion,
}:
{
  lock,
  fetchers ? { },
  packageOverrides ? { },
}:
let
  checked = purifier.checkLock lock;
  tree = purifier.tree (
    {
      name = "octave-fixed-sources";
      inherit (checked) entries;
      inherit
        runCommand
        fetchurl
        python3
        writeText
        ;
    }
    // fetchers
  );
  packages = builtins.listToAttrs (
    map (node: {
      name = node.name;
      value =
        let
          dependencies = builtins.filter (d: d.package != "octave") node.native.depends;
          base =
            if builtins.hasAttr node.name octave.pkgs then
              octave.pkgs.${node.name}
            else
              octave.pkgs.buildOctavePackage {
                pname = node.name;
                version = node.native.version;
                src = tree + "/${node.entry}";
              };
          prepared = base.overrideAttrs (old: {
            name = "octave-purified-${node.name}-${node.native.version}";
            version = node.native.version;
            src = tree + "/${node.entry}";
            requiredOctavePackages = map (d: packages.${d.package}) dependencies;
            buildInputs =
              (builtins.filter (p: !(p.isOctavePackage or false)) (old.buildInputs or [ ]))
              ++ map (d: packages.${d.package}) dependencies;
            env = (old.env or { }) // {
              TAR_OPTIONS = "--sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner";
              GZIP = "-n";
            };
            preBuild = ''
              export OCTAVE_PATH=${nativePkg}
              export PURIFIER_ARCHIVE="$src" PURIFIER_EXPECTED=${writeText "octave-native-metadata.json" (builtins.toJSON node.native)}
              octave-cli --no-init-all --quiet --eval 'actual=jsondecode(jsonencode(purifier_metadata(getenv("PURIFIER_ARCHIVE"))));expected=jsondecode(fileread(getenv("PURIFIER_EXPECTED")));if(!isequal(actual,expected)),error("Native Octave archive metadata differs from lock");endif;'
            ''
            + "\n"
            + (old.preBuild or "");
            postBuild =
              (old.postBuild or "")
              + "\n"
              + ''
                ${python3}/bin/python3 ${../../octave_purifier/normalize-archives.py} "$out"
              '';
          });
        in
        if builtins.hasAttr node.name packageOverrides then
          prepared.overrideAttrs packageOverrides.${node.name}
        else
          prepared;
    }) checked.data.nodes
  );
  installed = (octave.withPackages (_: builtins.attrValues packages)).overrideAttrs (old: {
    postBuild = old.postBuild + ''
      sed -i '/^# Created by Octave /d' "$out/.octave_packages"
    '';
  });
  manifest = writeText "octave-lock-native.json" (builtins.toJSON checked.data);
  output = runCommand "octave-locked-environment" { nativeBuildInputs = [ octave ]; } ''
    mkdir -p "$out"
    cp ${manifest} "$out/manifest.json"
    export OCTAVE_ENVIRONMENT=${installed}
    octave-cli --no-init-all --quiet --eval 'global_packages={};${
      lib.optionalString (checked.data.nodes != [ ])
        ''global_packages=load(fullfile(getenv("OCTAVE_ENVIRONMENT"),".octave_packages")).local_packages;''
    }save_header_format_string("");save("-text",[getenv("out"),"/global-registry"],"global_packages");'
    ln -s ${installed} "$out/packages"
    ln -s ${tree} "$out/sources"
  '';
in
assert lib.assertMsg (checked.data.sdk == sdkVersion) "Octave SDK changed; update the lock";
{
  inherit output packages tree;
}

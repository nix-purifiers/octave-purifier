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
  gnutar,
  gzip,
}@scope:
{
  src,
  lockFile ? src + "/octave-purifier.lock.json",
  fetchers ? { },
  packageOverrides ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
  buildCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  prepared = import ./environment.nix (builtins.removeAttrs scope [
    "gnutar"
    "gzip"
  ]) { inherit lock fetchers packageOverrides; };
  rawSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".octave-purifier"
        "result"
        "__pycache__"
      ]);
  };
  source = runCommand "octave-validated-source" { nativeBuildInputs = [ octave ]; } ''
    ${lib.optionalString (lock.data.project != null) ''
      export OCTAVE_PATH=${nativePkg}
      export PURIFIER_SOURCE=${rawSource} PURIFIER_EXPECTED=${writeText "octave-project-metadata.json" (builtins.toJSON lock.data.project)}
      octave-cli --no-init-all --quiet --eval 'actual=jsondecode(jsonencode(purifier_metadata(getenv("PURIFIER_SOURCE"))));expected=jsondecode(fileread(getenv("PURIFIER_EXPECTED")));if(!isequal(actual,expected)),error("Native Octave project metadata differs from lock");endif;'
    ''}
    mkdir -p "$out"
    cp -pr ${rawSource}/. "$out/"
  '';
  binary = octave.pkgs.buildOctavePackage {
    pname = lock.data.project.name;
    version = lock.data.project.version;
    src = source;
    requiredOctavePackages = builtins.attrValues prepared.packages;
    inherit nativeBuildInputs;
    postBuild = ''
      ${python3}/bin/python3 ${../octave_purifier/normalize-archives.py} "$out"
    '';
    env = {
      TAR_OPTIONS = "--sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner";
      GZIP = "-n";
    };
  };
  projectEnvironment =
    (octave.withPackages (
      _: (builtins.attrValues prepared.packages) ++ lib.optional (lock.data.project != null) binary
    )).overrideAttrs
      (old: {
        postBuild = old.postBuild + ''
          sed -i '/^# Created by Octave /d' "$out/.octave_packages"
        '';
      });
  project =
    runCommand "octave-project"
      {
        nativeBuildInputs = [
          projectEnvironment
          gnutar
          gzip
        ]
        ++ nativeBuildInputs;
      }
      ''
        mkdir -p "$out/source"
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ln -s ${projectEnvironment} "$out/environment"
      '';
  release =
    runCommand "octave-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" source/project
        cp -pr ${source}/. source/project/
        chmod -R u+rwX source
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/${
          if lock.data.project == null then
            "octave-project"
          else
            "${lock.data.project.name}-${lock.data.project.version}"
        }.tar.gz" -C source project
      '';
in
assert lib.assertMsg (lock.data.sdk == sdkVersion) "Octave SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}

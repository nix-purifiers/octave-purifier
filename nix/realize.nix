{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc;
    inherit (pkgs) octave lib;
  };
  nativePkg = pkgs.callPackage ./native.nix { };
  build = pkgs.callPackage ./build-project.nix { inherit purifier sdkVersion nativePkg; } {
    src = /. + project;
    lockFile = /. + companion;
  };
  output =
    if target == "environment" then
      build.packages.environment
    else if target == "release" then
      build.release
    else
      throw "Unknown Octave target";
in
if profile then
  pkgs.writeText "octave-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output

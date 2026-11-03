{
  lib,
  octave,
  nixpkgsSrc,
}:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    version = octave.version;
    source = toString octave.src;
    adapter = builtins.hashFile "sha256" ../octave_purifier/patch-sdk.py;
    metadata = builtins.hashFile "sha256" ../octave_purifier/purifier_metadata.m;
  }
)

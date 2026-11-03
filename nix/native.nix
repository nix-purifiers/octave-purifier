{
  runCommand,
  octave,
  python3,
}:
runCommand "octave-purifier-native" { nativeBuildInputs = [ python3 ]; } ''
  mkdir -p "$out"
  cp -r ${octave}/share/octave/${octave.version}/m/pkg/. "$out/"
  chmod -R u+w "$out"
  python3 ${../octave_purifier/patch-sdk.py} "$out"
  cp ${../octave_purifier/purifier_metadata.m} "$out/purifier_metadata.m"
''

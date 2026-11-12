{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  octave,
  nativePkg,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
  gcc,
  gfortran,
  gnumake,
  gnutar,
  gzip,
  coreutils,
  gnused,
  gnugrep,
  gawk,
  findutils,
  binutils,
  cacert,
}:
stdenvNoCC.mkDerivation {
  pname = "octave-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/octave-purifier"
    cp -r octave_purifier nix lib-overlays pkgs "$out/lib/octave-purifier/"
    install -m755 bin/octave-purifier "$out/bin/octave-purifier"
    substituteInPlace "$out/lib/octave-purifier/nix/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/octave-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          gcc
          gfortran
          gnumake
          gnutar
          gzip
          coreutils
          gnused
          gnugrep
          gawk
          findutils
          binutils
          octave
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default OCTAVE_PURIFIER_GH ${gh}/bin/gh \
      --set OCTAVE_PURIFIER_ORIGINAL ${octave}/bin/octave-cli \
      --set OCTAVE_PURIFIER_ORIGINAL_GUI ${octave}/bin/octave \
      --set OCTAVE_PURIFIER_NATIVE ${nativePkg} \
      --set OCTAVE_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set OCTAVE_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/octave-purifier" "$out/bin/octave-cli" --add-flags '--native=octave-cli'
    makeWrapper "$out/bin/octave-purifier" "$out/bin/octave" --add-flags '--native=octave'
    ln -s ${octave}/bin/mkoctfile "$out/bin/mkoctfile"
  '';
  meta = {
    description = "Native Octave with locked Nix-resolved packages";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "octave-purifier";
  };
}

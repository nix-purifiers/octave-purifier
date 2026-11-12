{
  description = "Locked, Nix-resolved Octave packages";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        octave-purifier = final.lib.makeScope final.newScope (scope: {
          nativePkg = scope.callPackage ./nix/native.nix { };
          sdkVersion = import ./nix/sdk-version.nix {
            nixpkgsSrc = nixpkgs;
            inherit (final) lib octave;
          };
          cli = scope.callPackage ./pkgs/octave-purifier/default.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildOctaveProject = scope.callPackage ./pkgs/build-octave-project/default.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).octave-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/octave-purifier";
          meta.description = "Lock native Octave packages";
        };
      });
      lib.octave-purifier = import ./lib-overlays/default { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.octave-purifier.buildOctaveProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = "octave-cli --quiet --eval 'pkg load purifierproof; assert(purifier_answer(),42);'";
          };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}

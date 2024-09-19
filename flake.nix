# flake.nix
# Allow to create virtual envs and install packahes on it
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/release-24.05";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      fhs = pkgs.buildFHSUserEnv {
        name = "kod";
        targetPkgs = pkgs: with pkgs; [
            python311
            poetry
            pyright
            lua
            (with python311.pkgs; [
                pip
                virtualenv
            ])
            glib
            zlib
            # pkgs.nodePackages.pyright
        ];
        runScript = "zsh";
        # runScript = "fish";
        # runScript = "poetry shell";
      };
    in
      {
        devShells.${system}.default = fhs.env;
      };
}
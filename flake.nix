# flake.nix
# Allow to create virtual envs and install packahes on it
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/release-24.11";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      fhs = pkgs.buildFHSUserEnv {
        name = "kod";
        targetPkgs = pkgs: with pkgs; [
            python312
            poetry
            pyright
            lua
            uv
            (with python312.pkgs; [
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

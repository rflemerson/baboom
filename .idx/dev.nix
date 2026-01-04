# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.python314
    pkgs.ruff
    pkgs.djlint
  ];

  # Sets environment variables in the workspace
  env = {
    PYTHONPATH = ".";
  };

  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      "ms-python.python"
      "batisteo.vscode-django"
      "bradlc.vscode-tailwindcss"
      "charliermarsh.ruff"
    ];

    # Enable previews
    previews = {
      enable = true;
      previews = {
        web = {
          # Example: run "npm run dev" with PORT set to IDX's defined port for previews,
          # and show it in IDX's web preview panel
          command = ["python" "manage.py" "runserver" "0.0.0.0:$PORT"];
          manager = "web";
          env = {
            # Environment variables for this preview
            PORT = "$PORT";
          };
        };
      };
    };

    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        # Open editors for the following files by default, if they exist:
        default.openFiles = [ "README.md" "AGENTS.md" ];
        install = "pip install -e .[dev]";
        migrate = "python manage.py migrate";
      };
      # Runs when the workspace is (re)started
      onStart = {
        # Example: start a background task to watch and re-build backend code
        # watch-backend = "npm run watch-backend";
      };
    };
  };

  # Services
  services = {
    postgres = {
      enable = true;
      package = pkgs.postgresql_15;
    };
    redis = {
      enable = true;
    };
  };
}

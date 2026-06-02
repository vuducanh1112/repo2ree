{
  description = "Fullstack Dev Environment with Node 25, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };

        # ----------------------------------------------------------------
        # Workbench image
        #
        # Builds a minimal OCI image that hosts a single REE. The host's
        # WorkbenchManager runs one of these per REE, mounts the REE
        # volume at /ree, and dispatches typed Commands via `docker exec`.
        #
        # Build with:   nix build .#workbench-image
        # Load with:    docker load < result
        # ----------------------------------------------------------------

        # Python runtime carrying only what `repo2ree_cli.cli` reaches at
        # import time. Keep this list minimal — adding deps here grows the
        # image and bypasses the reproducibility surface we're trying to
        # keep small.
        workbenchPython = pkgs.python313.withPackages (ps: with ps; [
          click
          pydantic
        ]);

        # Filter to just the Python sources so unrelated repo files don't
        # invalidate the image hash on every edit.
        repo2reeCoreSrc = pkgs.lib.cleanSourceWith {
          src = ./core/src;
          filter = path: type:
            let base = baseNameOf path; in
            !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
            && !(pkgs.lib.hasSuffix ".pyc" base);
        };

        repo2reeCliSrc = pkgs.lib.cleanSourceWith {
          src = ./cli/src;
          filter = path: type:
            let base = baseNameOf path; in
            !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
            && !(pkgs.lib.hasSuffix ".pyc" base);
        };

        # `repo2ree` entrypoint script. Adds the source dirs to PYTHONPATH
        # and dispatches through the CLI's __main__.
        repo2reeBin = pkgs.writeShellScriptBin "repo2ree" ''
          export PYTHONPATH="${repo2reeCoreSrc}:${repo2reeCliSrc}''${PYTHONPATH:+:$PYTHONPATH}"
          exec ${workbenchPython}/bin/python -m repo2ree_cli "$@"
        '';

        # Dev/test workbench entrypoint. It starts an in-container Docker
        # daemon so REE build scripts can run `docker build` without seeing
        # the host Docker socket. This image must be launched privileged.
        workbenchEntrypoint = pkgs.writeShellScriptBin "repo2ree-workbench-entrypoint" ''
          set -eu

          export PATH="${pkgs.docker}/bin:${pkgs.git}/bin:${pkgs.coreutils}/bin:${pkgs.bash}/bin:${pkgs.gnugrep}/bin:${pkgs.gnused}/bin:${pkgs.iproute2}/bin:${pkgs.iptables}/bin:$PATH"
          export DOCKER_HOST="unix:///var/run/docker.sock"
          export DOCKER_TLS_CERTDIR=""

          mkdir -p /var/lib/docker /var/run /run /tmp /ree

          if [ ! -S /var/run/docker.sock ]; then
            storage_driver="''${DOCKER_DRIVER:-vfs}"
            dockerd \
              --host=unix:///var/run/docker.sock \
              --data-root=/var/lib/docker \
              --exec-root=/var/run/docker \
              --storage-driver="$storage_driver" \
              > /var/log/dockerd.log 2>&1 &
          fi

          for _ in $(seq 1 60); do
            if docker info > /dev/null 2>&1; then
              break
            fi
            sleep 1
          done

          if ! docker info > /dev/null 2>&1; then
            echo "dockerd did not become ready; last log lines:" >&2
            tail -n 100 /var/log/dockerd.log >&2 || true
            exit 1
          fi

          exec "$@"
        '';

        workbenchImage = pkgs.dockerTools.buildLayeredImage {
          name = "repo2ree-workbench";
          tag = "latest";

          contents = [
            repo2reeBin
            workbenchEntrypoint
            workbenchPython

            # System tools the handlers shell out to.
            pkgs.git
            pkgs.docker
            pkgs.iproute2
            pkgs.iptables
            pkgs.renovate  # evaluate_dependency_score shells out to renovate
            pkgs.syft      # generate_sbom handler calls syft natively

            # Standard userland: sleep (entrypoint), mkdir, mv, etc.
            pkgs.coreutils
            pkgs.bash
            pkgs.gnugrep
            pkgs.gnused

            # TLS roots for https:// downloads in storage.fetch.
            pkgs.cacert
          ];

          config = {
            Entrypoint = [ "${workbenchEntrypoint}/bin/repo2ree-workbench-entrypoint" ];
            Cmd = [ "sleep" "infinity" ];
            WorkingDir = "/ree";
            Env = [
              "PATH=/bin"
              "DOCKER_HOST=unix:///var/run/docker.sock"
              "DOCKER_TLS_CERTDIR="
              "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
              "PYTHONDONTWRITEBYTECODE=1"
              "PYTHONUNBUFFERED=1"
            ];
          };
        };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [

            # Essentials
            git
            less
            vim
            docker-client

            # Project
            nodejs_25
            python313Packages.uv
            kubectl

            # graphviz for generating graphs with dependency cruiser
            graphviz

            # playwright browser drivers, because using nix and using playwright via npm does not work, since playwright
            # looks at default locations
            # fonts are important for the browsers to render properly
            playwright-driver.browsers
            fontconfig
            dejavu_fonts

          ];

          shellHook = ''
            if [ -t 1 ]; then
              echo "❄️  Nix Shell Loaded"
              echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
              export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
            fi

            export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
            export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="${pkgs.playwright-driver.browsers}/chromium_headless_shell-1200/chrome-linux/headless_shell"
            export FONTCONFIG_FILE=${pkgs.makeFontsConf { fontDirectories = [ pkgs.dejavu_fonts ]; }}
          '';
        };

        packages = {
          workbench-image = workbenchImage;
          default = workbenchImage;
        };
      });
}

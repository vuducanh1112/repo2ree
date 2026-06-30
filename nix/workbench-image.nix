# ----------------------------------------------------------------
# Workbench image
#
# Builds a minimal OCI image that hosts a single REE. The host's
# WorkbenchManager runs one of these per REE, mounts the REE
# volume at /ree, and dispatches typed Commands via `docker exec`.
#
# Build with:   nix build .#workbench-image
# Load with:    docker load < result
#
# This is a reproducibility-sensitive surface. The package list below
# is what every REE ships with — keep it minimal. Dev-only tooling
# belongs in ./devshell.nix, not here.
# ----------------------------------------------------------------
{ pkgs }:

let
  # Python runtime carrying only what `repo2ree_executor.cli` reaches at
  # import time. Keep this list minimal — adding deps here grows the
  # image and bypasses the reproducibility surface we're trying to
  # keep small.
  #
  # The opentelemetry trio backs the executor's span relay: spans are
  # encoded (proto-common) and streamed over stderr for the supervisor to
  # forward. The executor never talks to a collector itself, so the OTLP
  # HTTP exporter and `requests` are deliberately absent — those stay
  # behind the host-side functions in repo2ree_protocol.tracing.
  workbenchPython = pkgs.python313.withPackages (ps: with ps; [
    click
    pydantic
    opentelemetry-api
    opentelemetry-sdk
    opentelemetry-exporter-otlp-proto-common
  ]);

  # Filter to just the Python sources so unrelated repo files don't
  # invalidate the image hash on every edit.
  repo2reeProtocolSrc = pkgs.lib.cleanSourceWith {
    src = ../protocol/src;
    filter = path: type:
      let base = baseNameOf path; in
      !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
      && !(pkgs.lib.hasSuffix ".pyc" base);
  };

  repo2reeCoreSrc = pkgs.lib.cleanSourceWith {
    src = ../core/src;
    filter = path: type:
      let base = baseNameOf path; in
      !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
      && !(pkgs.lib.hasSuffix ".pyc" base);
  };

  repo2reeExecutorSrc = pkgs.lib.cleanSourceWith {
    src = ../executor/src;
    filter = path: type:
      let base = baseNameOf path; in
      !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
      && !(pkgs.lib.hasSuffix ".pyc" base);
  };

  # `repo2ree-exec` entrypoint script. Adds the source dirs to PYTHONPATH
  # and dispatches through the executor's __main__.
  repo2reeBin = pkgs.writeShellScriptBin "repo2ree-exec" ''
    export PYTHONPATH="${repo2reeProtocolSrc}:${repo2reeCoreSrc}:${repo2reeExecutorSrc}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${workbenchPython}/bin/python -m repo2ree_executor "$@"
  '';

  # Dev/test workbench entrypoint. It starts an in-container Docker
  # daemon so REE build scripts can run `docker build` without seeing
  # the host Docker socket. This image must be launched privileged.
  workbenchEntrypoint = pkgs.writeShellScriptBin "repo2ree-workbench-entrypoint" ''
    set -eu

    export PATH="${pkgs.docker}/bin:${pkgs.git}/bin:${pkgs.coreutils}/bin:${pkgs.bash}/bin:${pkgs.gnugrep}/bin:${pkgs.gnused}/bin:${pkgs.iproute2}/bin:${pkgs.iptables}/bin:$PATH"
    export DOCKER_HOST="unix:///var/run/docker.sock"
    export DOCKER_TLS_CERTDIR=""

    mkdir -p /var/lib/docker /var/log /var/run /run /tmp /ree

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
in
pkgs.dockerTools.buildLayeredImage {
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

    # Source acquisition: acquire_source.sh extracts the snapshot (tar/gzip) or
    # fetches an origin archive (curl + tar/unzip). The same script runs in a
    # downloaded bundle, so these mirror the reproducer's prerequisites.
    pkgs.gnutar
    pkgs.gzip
    pkgs.curl
    pkgs.unzip

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
}

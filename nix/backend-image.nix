{
  pkgs,
  buildRevision ? "development",
}:

let
  api = import ./python-closure.nix {
    inherit pkgs;
    name = "api";
  };

  users = pkgs.dockerTools.fakeNss.override {
    extraPasswdLines = [ "app:x:1000:1000:app:/app:/bin/false" ];
    extraGroupLines = [ "app:x:1000:" ];
  };
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-backend";
  tag = "local";

  contents = [
    api.env
    users
    pkgs.cacert
  ];

  fakeRootCommands = ''
    test -s ${api.imports}
    mkdir -p app/.repo2ree tmp
    chown -R 1000:1000 app
    chmod 1777 tmp
  '';
  enableFakechroot = false;

  config = {
    Labels = {
      "org.opencontainers.image.revision" = buildRevision;
    };
    User = "1000:1000";
    WorkingDir = "/app";
    Entrypoint = [
      "${api.env}/bin/python"
      "-m"
      "uvicorn"
      "repo2ree_api.main:app"
      "--host"
      "0.0.0.0"
      "--port"
      "8000"
    ];
    ExposedPorts = {
      "8000/tcp" = { };
    };
    Env = [
      "HOME=/app"
      "REPO2REE_BUILD_REVISION=${buildRevision}"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
    ];
  };
}

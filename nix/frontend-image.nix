# ----------------------------------------------------------------
# Frontend image
#
# Builds the Vite app at `nix build` time with buildNpmPackage (reads
# package-lock.json, fetches deps with hash verification) and ships the
# static `dist/` behind caddy. No Node in the runtime image.
#
# Toolchain provenance comes from the pinned nixpkgs in flake.lock — the
# same revision the dev shell and workbench image use — so the deployed
# bundle can't drift onto a different Node/npm than we develop against.
#
# Build with:   nix build .#frontend-image
# Load with:    docker load < result
#
# VITE_API_BASE_URL is baked in at build time (empty string => same-origin
# "/api"), matching the previous Dockerfile ARG semantics. Override with:
#   nix build .#frontend-image --argstr viteApiBaseUrl http://host:8000
# (wired through flake.nix).
# ----------------------------------------------------------------
{
  pkgs,
  viteApiBaseUrl ? "",
}:

let
  # Filter to the inputs that actually affect the build so unrelated repo
  # edits (tests, docs) don't invalidate the image hash.
  frontendSrc = pkgs.lib.cleanSourceWith {
    src = ../frontend;
    filter =
      path: _type:
      let
        base = baseNameOf path;
      in
      base != "node_modules"
      && base != "dist"
      && base != "tests"
      && !(pkgs.lib.hasPrefix "." base && base != ".");
  };

  frontendDist = pkgs.buildNpmPackage {
    pname = "repo2ree-web";
    version = "0.1.0";

    src = frontendSrc;

    # The hash of the fetched npm dependency set. It is not hand-maintained:
    # it lives in ./frontend-npm-deps.hash and is regenerated from
    # frontend/package-lock.json by `make frontend-npm-hash` (run after any
    # lockfile change). That target uses prefetch-npm-deps — the same tool
    # buildNpmPackage uses internally — so the file can never disagree with
    # what the build expects.
    #
    # (importNpmLock would drop the hash entirely, but it fails to prefetch
    # some transitive dev deps for this lockfile, so we stay on the hash path.)
    npmDepsHash = pkgs.lib.fileContents ./frontend-npm-deps.hash;

    # Baked into the bundle at build time.
    VITE_API_BASE_URL = viteApiBaseUrl;

    # The default install phase expects a CLI-style package; for a static
    # site we just copy the Vite output to $out.
    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -r dist/* $out/
      runHook postInstall
    '';

    # No test/lint at image-build time — that's CI's job, and pulling the
    # browser/test toolchain here would bloat the closure.
    npmFlags = [ "--ignore-scripts" ];
    dontNpmInstall = true;
  };

  # Caddy serves two things on one origin (port 3000):
  #
  #   /api/*  -> reverse-proxied to the backend. Because the frontend talks
  #              to the same origin it was served from, the browser makes no
  #              cross-origin request and there's no CORS to configure. The
  #              backend serves /api/v1/... natively, so no path rewrite.
  #   /*      -> the static Vite bundle, with SPA fallback. The app uses
  #              react-router (v6, client-side), so any non-asset path must
  #              serve index.html or deep links 404 on refresh.
  #
  # The backend upstream is a *runtime* env var ({$...:default}), not baked
  # into the image. The default `backend:8000` is the docker-compose service
  # name, resolved by the compose network — so `docker compose up` needs no
  # configuration. Override with BACKEND_UPSTREAM for other deployments.
  #
  # Hashed assets get a long immutable cache; index.html stays fresh so new
  # bundle hashes are picked up on the next load.
  caddyfile = pkgs.writeText "Caddyfile" ''
    {
      admin off
      auto_https off
    }

    :3000 {
      handle /api/* {
        reverse_proxy {$BACKEND_UPSTREAM:backend:8000}
      }

      handle {
        root * ${frontendDist}
        encode gzip zstd

        # Hashed assets are content-addressed, so cache them forever. Everything
        # else (the SPA shell served at / and on deep-link fallbacks) must stay
        # fresh so a redeploy is picked up on the next load. We can't key the
        # no-cache header off /index.html: `header` runs before `try_files`
        # rewrites the path, so on / and deep links the request path isn't
        # /index.html yet and the header would never apply. Match by "not an
        # asset" instead.
        @assets path /assets/*
        header @assets Cache-Control "public, max-age=31536000, immutable"
        @html not path /assets/*
        header @html Cache-Control "no-cache"

        try_files {path} /index.html
        file_server
      }
    }
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-frontend";
  # "local" marks never-pushed workbench builds; published channels (edge,
  # commit shas) are minted at push time in the Makefile.
  tag = "local";

  contents = [
    pkgs.caddy
    pkgs.cacert
    # Caddy needs a writable /tmp and the static root; coreutils/bash are
    # not required at runtime since we exec caddy directly.
  ];

  # Caddy needs some writable dirs and /etc/ssl roots at runtime.
  extraCommands = ''
    mkdir -p tmp
    chmod 1777 tmp
  '';

  config = {
    Entrypoint = [
      "${pkgs.caddy}/bin/caddy"
      "run"
      "--config"
      "${caddyfile}"
      "--adapter"
      "caddyfile"
    ];
    ExposedPorts = {
      "3000/tcp" = { };
    };
    Env = [
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "XDG_CONFIG_HOME=/tmp"
      "XDG_DATA_HOME=/tmp"
    ];
  };
}

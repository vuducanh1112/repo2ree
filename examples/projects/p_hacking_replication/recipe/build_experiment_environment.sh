#!/usr/bin/env sh
set -eu

# R 4.4.3, the version renv.lock names, from Rocker by digest; Quarto, which run_all.R renders with and
# the lock does not pin, by its release checksum. renv restores the lock's packages, from its dated
# Posit Package Manager snapshot, into R's site library, and the project's own renv activation is
# switched off, so every R process sees them: Rscript and the one Quarto starts per document alike.
IMAGE=ree-p-hacking-replication:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

CONTEXT=$(mktemp -d)
trap 'rm -rf "$CONTEXT"' EXIT
cp renv.lock "$CONTEXT/renv.lock"
cat > "$CONTEXT/Dockerfile" <<'EOF'
FROM rocker/r-ver:4.4.3@sha256:3dae5d2eeddf74f10e0a81fb6b7ae350295e288000304f438b844b2c1e00fe2c

ADD --checksum=sha256:6b83c1c9b6f2ce6454798b42260bd2ee184551d74debe817b8aaf28b09ac22d0 \
    https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz /tmp/quarto.tar.gz
RUN mkdir /opt/quarto \
    && tar -xzf /tmp/quarto.tar.gz -C /opt/quarto --strip-components=1 \
    && rm /tmp/quarto.tar.gz \
    && ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto

# The system libraries the lock's packages link against, as renv::sysreqs() names them for Ubuntu 24.04,
# from Ubuntu's archive as it was when the base image was built (its packages may not go back). It carries
# noble-security too, and only its URI is snapshotted.
RUN sed -i 's#http://security.ubuntu.com/ubuntu/#http://archive.ubuntu.com/ubuntu/#' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update --snapshot 20260311T120000Z \
    && apt-get install -y --no-install-recommends --snapshot 20260311T120000Z \
        cmake gdal-bin libcurl4-openssl-dev libfontconfig1-dev libfreetype6-dev libgdal-dev libgsl0-dev \
        libicu-dev libnode-dev libssl-dev libx11-dev libxml2-dev make pandoc zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV RENV_ACTIVATE_PROJECT=FALSE
COPY renv.lock /opt/renv.lock
RUN R -s -e 'install.packages("renv", repos = "https://packagemanager.posit.co/cran/2025-09-27")' \
    && R -s -e 'renv::restore(lockfile = "/opt/renv.lock", library = .Library.site[1], prompt = FALSE)'
EOF

docker build --tag "$IMAGE" "$CONTEXT"

mkdir -p "$(dirname "$EXPERIMENT_ENVIRONMENT_ARTIFACT")"
docker save "$IMAGE" --output "$EXPERIMENT_ENVIRONMENT_ARTIFACT"

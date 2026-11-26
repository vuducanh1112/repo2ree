#!/usr/bin/env sh
set -eu

# The capsule's own environment/Dockerfile, pinned. It starts from Code Ocean's R 4.4.2 image, here by digest,
# and installs its packages from Posit Package Manager's latest binaries, here as they were on 2026-05-04, the
# day the capsule's version 1.0 was published; patchwork it installs from GitHub as it is on the day of the
# build, here at the commit that was its newest on that day. plm, which the third stage loads and the capsule
# does not install (its run.sh runs the projection alone), comes from the same day. The versions installed are
# listed in /opt/r-packages.tsv.
IMAGE=ree-heat-suicide-projection:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

CONTEXT=$(mktemp -d)
trap 'rm -rf "$CONTEXT"' EXIT
cat > "$CONTEXT/Dockerfile" <<'DOCKERFILE'
FROM registry.codeocean.com/codeocean/py-r@sha256:405137d58b9589fc24d9374b9a0637a57cfd6020ab707db8d8f854a40def42d3

ARG DEBIAN_FRONTEND=noninteractive
ENV OPENBLAS_CORETYPE=Nehalem OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

RUN R -s -e 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/jammy/2026-05-04")); \
      install.packages(c("dplyr", "tidyr", "MASS", "ggplot2", "tsModel", "dlnm", "gnm", "splines", "mixmeta", \
        "mvmeta", "purrr", "reshape2", "gridExtra", "cowplot"))' \
    && R -s -e 'install.packages("plm", repos = "https://packagemanager.posit.co/cran/__linux__/jammy/2026-05-04")' \
    && R -s -e 'options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/jammy/2026-05-04")); \
      remotes::install_github("thomasp85/patchwork@6b1d88ce1da1c5cae3818d984edf80dc0bb3de8c", upgrade = "never")' \
    && R -s -e 'installed <- installed.packages()[, c("Package", "Version", "LibPath")]; \
      write.table(installed[order(installed[, "Package"]), ], "/opt/r-packages.tsv", sep = "\t", quote = FALSE, row.names = FALSE)'
DOCKERFILE

docker build --tag "$IMAGE" "$CONTEXT"

mkdir -p "$(dirname "$EXPERIMENT_ENVIRONMENT_ARTIFACT")"
docker save "$IMAGE" --output "$EXPERIMENT_ENVIRONMENT_ARTIFACT"

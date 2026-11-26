#!/usr/bin/env sh
set -eu

# The ARC's own workflows/R_environment/Dockerfile is a draft, never built: it names R 4.5.3 and the versions
# of eight packages the Methods give, and takes everything else from CRAN as it is on the day of the build.
# This one builds it pinned. R 4.5.3 from Rocker by digest; every package from Posit Package Manager as it
# was on 2026-08-31, the last day on which it served seven of the eight at the Methods' versions (lme4 2.0-6,
# nlme 3.1-170, glmmTMB 1.1.14, emmeans 2.0.4, vegan 2.7-5, patchwork 1.3.2, tidyverse 2.0.0); blme 1.0-8,
# the eighth, came out after vegan 2.7-5 was gone, and comes from a later day. The versions installed are
# listed in /opt/r-packages.tsv.
IMAGE=ree-trr341-drought-camelina:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

CONTEXT=$(mktemp -d)
trap 'rm -rf "$CONTEXT"' EXIT
cat > "$CONTEXT/Dockerfile" <<'DOCKERFILE'
FROM rocker/r-ver:4.5.3@sha256:f5a72ffeea7ed592b2a5990f87101beef8ef3cae0e4ff7327088e80368f0aef9

# R's reference BLAS and LAPACK, which the image carries next to OpenBLAS, in its place: one kernel on every
# CPU, on one thread, as R on Windows, where the authors ran the workflows, has them.
RUN update-alternatives --set libblas.so.3-x86_64-linux-gnu /usr/lib/x86_64-linux-gnu/blas/libblas.so.3 \
    && update-alternatives --set liblapack.so.3-x86_64-linux-gnu /usr/lib/x86_64-linux-gnu/lapack/liblapack.so.3

# The system libraries the packages' binaries link against, from Ubuntu's archive as it was when the base
# image was built. It carries noble-security too, and only its URI is snapshotted.
RUN sed -i 's#http://security.ubuntu.com/ubuntu/#http://archive.ubuntu.com/ubuntu/#' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update --snapshot 20261029T120000Z \
    && apt-get install -y --no-install-recommends --snapshot 20261029T120000Z \
        libcairo2 libcurl4t64 libfontconfig1 libfreetype6 libfribidi0 libharfbuzz0b libicu74 libjpeg-turbo8 \
        libpng16-16t64 libtiff6 libwebp7 libxml2 libxt6t64 \
    && rm -rf /var/lib/apt/lists/*

RUN R -s -e 'options(repos = c(CRAN = "https://p3m.dev/cran/__linux__/noble/2026-08-31")); \
      install.packages(c("blme", "car", "DHARMa", "dplyr", "emmeans", "ggplot2", "ggrepel", "glmmTMB", "lme4", \
        "lmerTest", "nlme", "openxlsx", "patchwork", "readr", "stringr", "tibble", "tidyr", "tidyverse", "vegan"))' \
    && R -s -e 'install.packages("blme", repos = "https://p3m.dev/cran/__linux__/noble/2026-10-15", dependencies = FALSE)' \
    && R -s -e 'wanted <- c(lme4 = "2.0.6", nlme = "3.1.170", glmmTMB = "1.1.14", blme = "1.0.8", emmeans = "2.0.4", \
        vegan = "2.7.5", tidyverse = "2.0.0", patchwork = "1.3.2"); \
      got <- vapply(names(wanted), function(p) as.character(packageVersion(p)), ""); \
      if (any(got != wanted)) stop("not the Methods versions: ", paste(names(got), got, collapse = ", ")); \
      installed <- installed.packages()[, c("Package", "Version", "LibPath")]; \
      write.table(installed[order(installed[, "Package"]), ], "/opt/r-packages.tsv", sep = "\t", quote = FALSE, row.names = FALSE)'
DOCKERFILE

docker build --tag "$IMAGE" "$CONTEXT"

mkdir -p "$(dirname "$EXPERIMENT_ENVIRONMENT_ARTIFACT")"
docker save "$IMAGE" --output "$EXPERIMENT_ENVIRONMENT_ARTIFACT"

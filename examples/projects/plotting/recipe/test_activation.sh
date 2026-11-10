#!/usr/bin/env sh
set -eu

python -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot; print('activation ok')"

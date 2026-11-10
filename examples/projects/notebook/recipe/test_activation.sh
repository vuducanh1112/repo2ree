#!/usr/bin/env sh
set -eu

jupyter kernelspec list | grep -q '^ *python3 '
python -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot, nbclient, numpy; print('activation ok')"

#!/usr/bin/env sh
set -eu

jupyter execute --output=executed source/decay.ipynb
mv source/executed.ipynb source/figure.png source/figure.json source/curve.csv source/result.txt .
cat result.txt

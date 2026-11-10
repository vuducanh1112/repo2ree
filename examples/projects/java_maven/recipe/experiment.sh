#!/usr/bin/env sh
set -eu

java -cp '/app/target/classes:/app/target/dependency/*' com.example.Main > result.txt
cat result.txt

#!/usr/bin/env sh
set -eu

# The claim: the workflow writes the one table the ARC holds in its run folder, the authors' own, byte for byte.
DHARMA='runs/TabS1_germination_AxT_by_condition/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/TabS1_germination_AxT_by_condition/*.tsv' 'runs/TabS1_germination_AxT_by_condition/*.txt' ":(exclude)$DHARMA"; }

if [ "$(tables --name-only --diff-filter=D)" != "" ]; then
  echo "tables the workflow should write are missing:" >&2
  tables --name-status --diff-filter=D >&2
  exit 1
fi
if [ -n "$(tables --name-only --diff-filter=ACRTUXB)" ]; then
  echo "the tables changed in other ways than in content:" >&2
  tables --name-status --diff-filter=ACRTUXB >&2
  exit 1
fi

if [ -n "$(tables --name-only --diff-filter=M)" ]; then
  echo "tables differ from the authors':" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi

echo "TabS1_germination_AxT_by_condition: 0 tables as this environment writes them, the rest as the authors wrote them"

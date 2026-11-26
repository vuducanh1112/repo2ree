#!/usr/bin/env sh
set -eu

# The claim: the workflow writes the one table the ARC holds in its run folder, and it differs from the authors'
# (R 4.5.3 on Windows) in digits the platform decides: it is pinned as this environment writes it.
DHARMA='runs/TabS3_mucilage_germination/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/TabS3_mucilage_germination/*.tsv' 'runs/TabS3_mucilage_germination/*.txt' ":(exclude)$DHARMA"; }

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

MODIFIED=$(cat <<'EOF'
fbf984b15b987bf8fcb9b0b1bd1643db524f08b770d3286588375fccb96e88a6  runs/TabS3_mucilage_germination/H2_mucilage_germination.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 1 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

echo "TabS3_mucilage_germination: 1 tables as this environment writes them, the rest as the authors wrote them"

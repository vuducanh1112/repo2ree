// Prefilled verify-script templates for the standard verification cases.
//
// A verify script is plain POSIX sh, run from the workspace root after the run
// script — exactly like the run script, with nothing injected into its
// environment. Its exit code is the verdict: 0 = the claimed result was
// reproduced. It reads whatever it checks straight from the workspace, so a
// check against the run's stdout expects the run script to have materialized it
// to a workspace file (e.g. `… | tee results/run.log`) — there are no magic
// variables handing over the captured streams.
//
// Templates carry EDIT-ME placeholders the author fills in and state the claim
// in a comment header. `set -e` makes the final check's exit status the verdict.

interface VerifyTemplate {
  key: string;
  label: string;
  description: string;
  body: string;
}

const HEADER = `#!/usr/bin/env sh
# Verify script — checks that the experiment produced its claimed result.
# Runs from the workspace root after the run script. Exit 0 = verified.
# Nothing is injected: read whatever you check straight from the workspace.
# To check the run's stdout, have the run script write it to a file, e.g.
#   <your run command> | tee results/run.log
set -eu
`;

export const DEFAULT_VERIFY_TEMPLATE = `${HEADER}
# Claim: the run log contains the expected phrase.
# RUN_LOG is the file the run script materialized its stdout to.
RUN_LOG='EDIT-ME results/run.log'
grep -Fq 'EDIT-ME expected phrase' "$RUN_LOG"
`;

export const VERIFY_TEMPLATES: VerifyTemplate[] = [
  {
    key: "stdout-contains",
    label: "Stdout contains",
    description: "The run log (stdout materialized to a file) must contain an expected phrase.",
    body: DEFAULT_VERIFY_TEMPLATE,
  },
  {
    key: "stdout-regex",
    label: "Stdout matches regex",
    description: "The run log must match an extended regular expression.",
    body: `${HEADER}
# Claim: the run log matches the expected pattern.
RUN_LOG='EDIT-ME results/run.log'
PATTERN='EDIT-ME: accuracy: 0\\.9[0-9]+'
grep -Eq "$PATTERN" "$RUN_LOG"
`,
  },
  {
    key: "numeric-tolerance",
    label: "Numeric within tolerance",
    description: "A number extracted from the run log must be within ± epsilon of the claim.",
    body: `${HEADER}
# Claim: the reported metric equals EXPECTED within ± EPSILON.
# EXTRACT_PATTERN pulls the number out of the run log (first match wins).
RUN_LOG='EDIT-ME results/run.log'
EXPECTED='EDIT-ME 0.9542'
EPSILON='EDIT-ME 0.001'
EXTRACT_PATTERN='[0-9]+\\.[0-9]+'
actual=$(grep -Eo "$EXTRACT_PATTERN" "$RUN_LOG" | head -n 1)
[ -n "$actual" ] || { echo "no number matching the extract pattern in $RUN_LOG" >&2; exit 1; }
awk -v a="$actual" -v e="$EXPECTED" -v eps="$EPSILON" \\
  'BEGIN { d = a - e; if (d < 0) d = -d; exit !(d <= eps) }'
`,
  },
  {
    key: "file-sha256",
    label: "Output file sha256",
    description: "A produced file must hash to a recorded sha256 baseline.",
    body: `${HEADER}
# Claim: the output file is byte-identical to the recorded baseline.
OUTPUT_FILE='EDIT-ME results/output.csv'
EXPECTED_SHA256='EDIT-ME paste the sha256 hex digest'
[ -f "$OUTPUT_FILE" ] || { echo "output file not found: $OUTPUT_FILE" >&2; exit 1; }
actual=$(sha256sum "$OUTPUT_FILE" | cut -d' ' -f1)
[ "$actual" = "$EXPECTED_SHA256" ] || { echo "digest mismatch: got $actual" >&2; exit 1; }
`,
  },
];

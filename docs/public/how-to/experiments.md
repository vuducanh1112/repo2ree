# Experiments in an REE

An experiment is a pair of script that 1) produces a result and 2) a check that decides whether the result is the being claimed.

This is the companion to [The runtime of an REE](build-runtimes.md). That guide
covers packaging the environment; this one covers what you execute inside it and
how the outcome becomes evidence.

## What an experiment is made of

Naming an experiment declares it on the REE and settles its reserved script
paths. From `figure-3`, repo2ree derives:

| Part | Where it lives | What it does |
|---|---|---|
| **Run script** | `ree-scripts/experiments/figure-3.sh` | Produces the result. Owns entering the runtime. |
| **Verify script** | `ree-scripts/experiments/figure-3.verify.sh` | Decides the verdict. Its exit code *is* the verdict. |
| **Output files** | declared paths in the workspace | The files the run produces, captured after every successful run. |

Names accept letters, digits, spaces, `.`, `_`, and `-`; spaces collapse to
hyphens in the derived slug. Name an experiment for the claim it settles —
`figure-3`, `table-2-ablation`, `smoke-test` — rather than for the mechanism.

![The experiment page: the saved run script that loads the runtime and runs the command, and the verify script below it with its starter templates](../tutorials/assets/create-first-ree/08-experiment.png)

Only the verify script is optional, and leaving it out has a cost: without a
declared criterion, a later review can only report `inconclusive`. An experiment
with no check is a command that ran, not a claim anyone can reproduce.

## The run script

The run script executes as `sh <path>` from the **workspace root**:

```sh
#!/usr/bin/env sh
set -eu

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime.tar"
IMAGE_TAG="ree-runtime:latest"
RUN_LOG="results/run.log"

# Loading from the saved artifact — not the locally built image — proves the
# artifact itself is self-contained.
docker load --input "$RUNTIME_ARTIFACT"

mkdir -p "$(dirname "$RUN_LOG")"
docker run --rm -v "$(pwd):/workspace" -w /workspace "$IMAGE_TAG" \
  python main.py > "$RUN_LOG"
cat "$RUN_LOG"
```

Three details in that template earn their place:

- **Load from the artifact, not from the daemon's image cache.** A run against
  an image that happens to sit in the local daemon proves nothing about the file
  the REE carries. Loading the artifact each time tests the thing that ships.
- **The workspace is bind-mounted, so outputs land in the workspace.** The
  environment comes from the runtime; the code and the results live in the
  workspace, where the verify script and the capture step can reach them.
- **Stdout goes to a file through a redirect, never `| tee`.** A pipeline
  reports the exit status of its *last* command, so `| tee` would mask a failing
  run as a pass. Redirect, then `cat` the file if you want the log on screen.

That last point matters more than it looks. Nothing captures stdout for the
verify script: **to check what a run printed, the run script has to materialize
it to a workspace file first.**

## The verify script

The verify script is the criterion, expressed as a plain script rather than as a
matcher configuration. It runs from the workspace root after the run script,
again with nothing injected, and **its exit code is the verdict — 0 means the
declared validation passed.**

It reads whatever it needs straight from the workspace. Four starter templates
cover the standard cases:

| Template | The claim it encodes |
|---|---|
| **Stdout contains** | The run log holds an expected phrase. |
| **Stdout matches regex** | The run log matches an extended regular expression. |
| **Numeric within tolerance** | A number extracted from the run log sits within ± epsilon of the claimed value. |
| **Output file sha256** | A produced file hashes to a recorded baseline. |

Each arrives with `EDIT-ME` placeholders on the parts that carry the claim, so an
unedited template fails rather than passing vacuously. The numeric one is the
most instructive:

```sh
#!/usr/bin/env sh
set -eu

# Claim: the reported metric equals EXPECTED within ± EPSILON.
RUN_LOG='EDIT-ME results/run.log'
EXPECTED='EDIT-ME 0.9542'
EPSILON='EDIT-ME 0.001'
EXTRACT_PATTERN='[0-9]+\.[0-9]+'
actual=$(grep -Eo "$EXTRACT_PATTERN" "$RUN_LOG" | head -n 1)
[ -n "$actual" ] || { echo "no number matching the extract pattern in $RUN_LOG" >&2; exit 1; }
awk -v a="$actual" -v e="$EXPECTED" -v eps="$EPSILON" \
  'BEGIN { d = a - e; if (d < 0) d = -d; exit !(d <= eps) }'
```

### Choose the criterion the science actually needs

Byte-exactness is one option among several, and often the wrong one. A run that
writes a timestamp, a hostname, or a floating-point sum computed in a different
thread order will differ byte-for-byte while agreeing perfectly on the claim.
Pick the weakest check that still fails when the result is wrong:

- an exact digest for artefacts that must not change at all;
- a tolerance for metrics;
- a structural check — row counts, schema, a key subset — for tabular output;
- a statistical test where the claim is distributional.

Writing it as a script is what makes this honest. A reviewer can read the check,
disagree with it, and say why — which is not possible when the criterion is
"the author eyeballed the figure".

## Example

The tutorial's pandas project declares one experiment, `python-hello`. Its run
script loads the runtime, runs `main.py` inside it with the workspace mounted,
and materializes stdout to `result.txt`:

```sh
#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
RUNTIME_FILE="python_hello_world/runtime.tar"

if ! docker image inspect "$IMAGE_NAME:$TAG" >/dev/null 2>&1; then
  docker load < "$RUNTIME_FILE"
fi

docker run --rm \
  -v "$(pwd):/workspace" \
  -w /workspace \
  "$IMAGE_NAME:$TAG" \
  python python_hello_world/main.py > "result.txt"
```

Its verify script reads that file back, and nothing else:

```sh
#!/usr/bin/env sh
set -eu

# The run script materialized its stdout to this workspace file; read it back.
EXPECTED="Pandas Hello World"
grep -Fq "$EXPECTED" "result.txt"
```

`result.txt` is then declared as the experiment's **output file**. Those three
pieces — run, check, declared output — are the whole contract.

## Output files and the author baseline

Declaring output files is what turns a run into evidence rather than a log line.
After every successful run, the workbench copies the declared paths into a
per-experiment results store and records their digest on the run receipt.

Capture is always local. An experiment can additionally **opt into sealing** its
results, which packages that captured baseline into the downloadable bundle at
`ree/results/<name>/`.

The distinction that trips people up: the sealed baseline is for *comparison*,
not for verification. A reviewer's fresh run writes its own outputs to the
declared paths in the workspace, and the verify script always reads that fresh
workspace — never the baseline sitting beside it. The baseline is what the
reviewer's result gets compared *against* afterwards.

## What a passing run means

A run whose script and verify script both exit 0 is **validated against its
declared check**. It is not a reproduction. Reproduction is the later comparison:
a fresh run, evaluated against the author's recorded baseline.

When a reviewer re-runs the experiment, the comparison settles on this ladder:

| Verdict | When |
|---|---|
| `inconclusive` | No verify script, no author baseline, the author's own verify never passed, or the reviewer ran a *different* criterion than the author recorded. |
| `different` | The author's criterion, applied to the reviewer's fresh outputs, exited nonzero. |
| `reproduced` | The criterion passed on the reviewer's outputs. |
| `identical` | It passed *and* both sides recorded the same output digest. |

Two asymmetries are deliberate. A criterion-digest mismatch downgrades to
`inconclusive`, because a different test cannot reproduce the old claim. An
output-digest mismatch never downgrades a passing verify, because timestamps,
seeds, and hostnames land in output files on every honest re-run.

The consequence for authors: **the verify script is the artefact a reviewer
inherits.** Change it after publishing and you have not tightened your evidence,
you have made the old claim unreproducible.

## Designing experiments that survive

- **One claim per experiment.** A single script that regenerates every figure in
  the paper produces one verdict for twelve claims. Split them so a failure
  names what broke.
- **Pin the randomness.** Seed every generator the run touches, and set
  `PYTHONHASHSEED` where hash ordering can leak into output. An unpinned seed
  turns a tolerance check into a coin flip.
- **Fetch nothing at run time.** Downloads at experiment time are an unrecorded
  dependency and a future failure. Bake data into the runtime, or declare it as
  an input.
- **Keep runs short where you can.** A reviewer with a ten-minute smoke test
  will run it; one facing a six-hour job may not. A cheap `smoke-test` beside
  the expensive experiments is worth the extra declaration.
- **Write outputs only to declared paths.** An undeclared output is not
  captured, not digested, and not comparable.
- **Do not chain experiments.** The workspace is reset before a reproduction
  run, so an experiment that silently depends on a previous one's leftovers
  passes for you and fails for everyone else.

## Pitfalls that bite in practice

- **A verify script that cannot fail.** `grep -q phrase results/run.log || true`,
  or a check against a file the run script never writes, passes without checking
  anything. Test it: break the run deliberately and confirm the verify script
  goes red.
- **Checking stdout that was never materialized.** Nothing captures stdout for
  the verify script. If the run script does not write it to a file, the verify
  script cannot read it.
- **`| tee` masking a failed run.** The pipeline's exit status belongs to `tee`.
  Redirect instead.
- **Verifying against the baseline instead of the fresh output.** A verify script
  that reads `ree/results/<name>/…` checks the author's own recorded answer and
  passes for everybody. Read the workspace.
- **Root-owned outputs.** A container running as root writes root-owned files
  into the mounted workspace. Run as a matching user, or expect files you cannot
  clean up.
- **An unconfigured generated scaffold.** A generated run script ships with an
  empty `set --` and exits **64** until you fill in the command. That is a
  refusal to guess your science, not a bug.
- **Output paths outside the workspace.** Scripts and outputs that resolve
  outside the workspace are rejected.

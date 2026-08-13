# How to verify a result

Verify is the reviewer and reader loop. The goal is to re-run a published
result and get a comparable record instead of informal notes.

## Current workflow

1. Open a published REE.
2. Inspect the Repro Label and archive metadata.
3. Start a review attempt and choose an evidence basis. `Auto` prefers an
   independent fetch; `Bundled` deliberately checks the source carried by the REE.
4. Reproduce source, build, and activation in order.
5. Re-run one or more experiments and apply the author's verify script to the
   reviewer's fresh outputs.
6. Inspect the per-step receipts, comparisons, evidence basis, and verdicts.

The current comparison records bind the reviewer evidence to the author
baseline and the criterion that was applied. A portable predecessor link that
turns the whole attempt into an independently citable verification artifact is
still target work.

## Current status

The current app implements the first end-to-end Verify loop:

- every attempt has an isolated source/overlay/workspace/evidence tree inside
  the REE workbench, while author evidence remains read-only;
- source identity is compared by SWHID;
- rebuilt runtimes are compared first by artifact digest, then by SBOM closure;
- activation records whether the runtime built by that attempt is inhabitable;
- experiments apply the same author-provided verify script to fresh outputs and
  compare output digests when both baselines exist;
- receipts, comparisons, logs, evidence bases, and verdicts are persisted and
  surfaced through the API and Review console.

An independently portable verification bundle, explicit receipt predecessor
links, reviewer signatures, and deposit of the review as its own citable
artifact are still target work.

An author run whose verify script passes is a **validated baseline**, not a
reproduction. The term reproduction is reserved for the later comparison: a
fresh run evaluated against that baseline, ideally recorded with a predecessor
link to the author's receipt.

## What Verify should compare

Not every result should be byte-exact. Some outputs need exact hashes, while
others need numeric tolerances, structured comparisons, statistical checks, or
manual review. Verify scripts make that chosen comparison explicit in code —
plain scripts whose exit code is the verdict.

## Captured results and the author baseline

An experiment declares the workspace files it produces (its output files). After
every successful run the workbench captures those files into a per-experiment
produced-results store and records their digest on the run receipt, so a later
seal can flag a result whose bytes changed in the shared workspace since it ran.

Capture is always local. An experiment can additionally **opt into sealing** its
results, which packages that captured baseline into the downloadable bundle at
`ree/results/<name>/`. That baseline is for comparison, not re-verification: a
reviewer's fresh run writes its own outputs to the declared paths in the
workspace, and can diff them against the author's baseline sitting outside the
workspace. Verify itself always reads the fresh workspace, never the baseline.

For the deeper design, see [Run Receipt](../reference/concepts.md#run-receipt).

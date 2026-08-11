# How to Verify a Result

Verify is the reviewer and reader loop. The goal is to re-run a published
result and get a comparable record instead of informal notes.

## Target workflow

1. Open a published REE.
2. Inspect the Repro Label and archive metadata.
3. Re-run one or more published Run Receipts.
4. Run the author-provided verify script against the new run evidence.
5. Save the verification as a new receipt that points back to the original.

That predecessor link matters. It turns "I tried to reproduce this" into a
structured relation between the author's evidence and the reviewer's evidence.

## Current status

The current app has the pieces needed for the first version of Verify:

- experiment commands can be declared and run;
- author-provided verify scripts run from the workspace root after the run and check whatever they read from it (a run that wants its stdout checked materializes it to a workspace file); their exit code is the verdict;
- logs and run status are captured;
- reviewer-facing preview and review paths exist in the app shape.

The durable verification receipt, receipt-to-receipt diff view, and citable
reviewer artifact are still target work.

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

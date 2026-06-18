# Verify a Result

Verify is the reviewer and reader loop. The goal is to re-run a published
result and get a comparable record instead of informal notes.

## Target workflow

1. Open a published REE.
2. Inspect the Repro Label and archive metadata.
3. Re-run one or more published Run Receipts.
4. Compare the new outputs against the declared output contracts.
5. Save the verification as a new receipt that points back to the original.

That predecessor link matters. It turns "I tried to reproduce this" into a
structured relation between the author's evidence and the reviewer's evidence.

## Current status

The current app has the pieces needed for the first version of Verify:

- experiment commands can be declared and run;
- expected outputs can be checked;
- logs and run status are captured;
- reviewer-facing preview and review paths exist in the app shape.

The durable verification receipt, receipt-to-receipt diff view, and citable
reviewer artifact are still target work.

## What Verify should compare

Not every result should be byte-exact. Some outputs need exact hashes, while
others need numeric tolerances, structured comparisons, statistical checks, or
manual review. Verify should make the chosen comparison explicit instead of
silently treating every difference as either failure or success.

For the deeper design, see [Run Receipt](../concepts.md#run-receipt).

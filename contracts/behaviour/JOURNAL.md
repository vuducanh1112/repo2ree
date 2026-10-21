# Behaviour journal contract

What an owner must write so that `repo2ree_conformance` can judge it. The record shapes
are in [`events.schema.json`](events.schema.json), generated from
`specifications/behaviour/vocabulary/`; this file states what a schema cannot. Both are
protected (`zones.toml`, spec): the product writes against them and never changes them.

Nothing here assumes a language. An owner may write its journal however it likes, and may
record more than the vocabulary declares: other subjects and other facts are its own and
never change a verdict. What the vocabulary declares must keep its meaning.

## Files

- One journal per process start (an **epoch**): `<process>-<epoch>.ndjson` in the
  journal directory, `<process>` matching `^[a-z][a-z0-9-]*$`, `<epoch>` six digits.
- The epoch is one more than the highest already in the directory, and the file is
  created exclusively (fail if it exists, then take the next): two processes never share
  an epoch. A missing earlier epoch makes every later one incomplete.
- One JSON object per line, UTF-8, `\n`-terminated. A line is complete only once its
  newline is written; a torn last line makes the journal incomplete.

## Records

Every line carries `"v": 1` and `seq`, an integer starting at 1 and increasing by exactly
one per line. Optional on every line: `at` (an ISO 8601 timestamp, never used for
order) and `trace` (`{"trace_id": 32 hex, "span_id": 16 hex}`, the span active when the
record was written; views use it, verdicts never do).

| `kind` | When | Fields |
|---|---|---|
| `journal.opened` | First line, `seq` 1 | `process`, `epoch` (as in the file name), `hosts` (every component the vocabulary places in this process, sorted), `vocabulary` (the `x-vocabulary` digest of the schema the owner wrote against; provenance only) |
| `transition` | An entity changed state | `owner`, `subject`, `key`, `partition`, `from` (null on creation), `to`, `facts` |
| `send` | The sender is about to send a boundary's request | `owner`, `subject`, `key`, `partition`, `message`, `facts` |
| `receive` | The sender observed a response | as `send` |
| `abandon` | The sender stopped waiting without any response | as `send`, with `message` null and `facts.reason` |
| `journal.closed` | Last line, on a deliberate stop | `final: true` when the owner will never resume (a decommissioned deployment, the end of a test stack) |

A fact recorded as `null` counts as absent. A required fact (the schema's `required`, the
vocabulary's `required` / `required_in`) must be present and not null.

## Sequence and durability

These are what make a lost record visible rather than silent:

1. **A number is consumed even when its write fails.** If writing line `n` fails, the next
   line is `n + 1`: the reader sees the gap. Never retry under the same number.
2. **Each line is durable before the call returns** (written and flushed to stable
   storage, `fsync` or equivalent).
3. **Record after the change, never before.** An owner journals a transition only after
   its own persisted state changed, so the journal may lag the owner but never runs ahead.
   The checker reconciles persisted state against the journal and treats a difference as
   a change that bypassed journaling.
4. **Nothing after `journal.closed`.** A closed journal stays closed; a restart opens a
   new epoch.
5. **One writer per file.** Concurrent writers in one process serialize through one
   sequence.

## Citations

Order across sources comes only from records that name each other (the rules in
`specifications/behaviour/boundaries/*.toml`). A journal record is named as
`<process>-<epoch>#<seq>`, which `send` must make available to the caller so it can travel
with the request (today: `ExecutionContext.dispatch_record`, recorded by core as the
attempt's `dispatched_by`). Without the citation the checker cannot order the two records,
and every rule that needs the order is inconclusive.

## Git evidence

Subjects with `evidence = "git"` (`Attempt`, `Ree`, `Step`) are not journaled: the checker
derives them from the REE's history (`refs/heads/ree-history` and the import refs a
downloaded archive keeps). Core's capture commit messages are `<operation>\n\n<record JSON>`,
and pending records live in `.git/repo2ree/operations/*.json`. The checker reads from a
record: `attempt_id`, `run_id`, `scope`, `command.operation`, `context.ree_id`,
`context.dispatch_record`, `operation_status`, `capture_status`, `capture_error`, `phases`
(each phase entered, in order), and `step_evidence_before` / `step_evidence_after`.
Whether the tree changed and whether `ree.json` carries a seal are read from Git itself.

## Checking a journal

```
python -m repo2ree_conformance validate-journal <file-or-directory>…
```

exits 1 and lists each problem when a journal breaks this contract: its file name, header,
sequence, or any record's shape. Any JSON Schema validator gives the same answer on the
records; the sequence and header rules are this command's alone.

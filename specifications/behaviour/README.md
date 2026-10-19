# Behaviour specification

This directory is the human-owned statement of how repo2ree behaves at runtime.
Implementation is checked against it: owners record what they do, Git witnesses
what the REE became, and `repo2ree_conformance` decides whether that evidence
conforms.

Review changes here carefully. Code that satisfies the checker does not need the
same line-by-line review; a wrong specification makes the checker approve wrong
code. A commit may change this directory or runtime code, not both (the
`spec-isolation` pre-commit hook).

## Model

| File | Declares |
|---|---|
| `components.toml` | Components and the process each runs in. A process journal speaks for the components it hosts. |
| `entities/*.toml` | State machines. Each has exactly one **owner** component; nothing else changes its state. |
| `boundaries/*.toml` | Request/response exchanges between components, recorded by the sender. `brackets` names entities whose work for key K happens inside exchange K. |
| `invariants.toml` | Cross-entity rules, each in one fixed pattern. |

| Entity / boundary | Owner | Evidence |
|---|---|---|
| `Run` | api (`JsonRunStore`) | API process journal, reconciled against `runs/*/state.json` |
| `Allocation` | supervisor (`AllocationStore`) | API process journal, reconciled against `allocations.json` |
| `dispatch` | supervisor → workbench (`dispatch_action`) | API process journal |
| `Attempt` | core (`capture_command`) | the REE's Git history: capture commits and pending records |
| `Ree` | core | **witnessed** from Git: a transition per commit whose tree changed, `sealed` iff the committed `ree.json` carries a seal |
| `Step` | core | core's `audit()` before and after each author attempt, recorded in the capture commit |

Not yet specified: reviews (they have their own histories), workbench sessions,
uploads, read-only queries, the REE index and deposits, and the workbench's side
of `dispatch`.

## Evidence and order

- **Journals** (`BEHAVIOUR_JOURNAL_DIR`, one `<process>-<epoch>.ndjson` per process
  start) carry contiguous sequence numbers, so a lost record is a visible gap. A
  journal closed deliberately ends with `journal.closed`.
- **Git** is core's journal. Facts that matter are read from Git itself where
  possible (tree changes, the seal), not from what the owner claims.
- **Stores** are the owners' persisted state, snapshotted after they stop. The
  `reconciliation` rule requires them to equal what the journals replay to, so a
  state change that bypassed journaling is a violation.

Order comes only from: positions within one source; epochs then positions within
one process's journals; and boundary brackets (an `Attempt` for key K happened
after `dispatch` K was sent and before its outcome was received). Wall-clock time
is never used.

## Patterns

| Pattern | Checked as |
|---|---|
| machine (per entity) | Transitions start where the last ended, follow declared edges, are recorded by the owner, carry declared facts, and never leave a terminal state. With `settles_before_close`, an entity must be terminal when its owner's journal closes. |
| exchange (per boundary) | Per key: one request, then at most one response or abandonment, never before the request, and not missing once the sender's journal closed. |
| `requires` | When the trigger occurs, the keyed entity reached a state (with facts) or the keyed message exists; with `order = "before"`, it happened before the trigger. |
| `response` | After the trigger, the entity eventually reaches one of the listed states. |
| `guard` | The triggering transition's facts satisfy a condition (for example: a receipt appears only through its own operation). |
| `excludes` | At the trigger, no entity of the given kind in the same partition is in the listed states. |
| reconciliation (implicit) | Persisted store state equals the journal replay. |

Triggers name target states (`to`), optionally source states (`from`, where
`(none)` means creation), and fact conditions (`where`). Conditions take a value,
`{ not = value }`, or `{ in = [values] }`; an absent fact never matches.

## Verdicts

- **violated**: complete evidence that covers the subject contradicts the specification.
- **inconclusive**: the evidence cannot decide: a journal gap, no source for the
  partition, an entity still in flight, events the evidence cannot order, journals
  written against another specification digest, or no behaviour at all.
- **passed**: every triggered rule held. A check where nothing triggered is inconclusive.

The CLI exits 0, 1, or 2. The demo stack fails a passing test whose evidence is violated.

## Views

`check -o DIR` writes `conformance.md`, `conformance.json`, and `conformance.html`:

- **System map**: processes ⊃ components ⊃ owned entities, boundaries, and invariants,
  drawn from this directory alone (`python -m repo2ree_conformance map`).
- **State machines** with each edge labelled by how often it was exercised; `0` is
  specified behaviour no evidence reached.
- **Specification diff**: `python -m repo2ree_conformance diff --base <ref>` draws
  added and removed edges, entities, invariants, and boundaries for review.

Views of a recording's evidence live in `repo2ree_traceview`, which reads the checker's
replayed model and verdicts and nothing else; OpenTelemetry spans are attached as context
and never change a verdict:

- **Operation trace** (`just trace-recording <recording>`): setup, the operations that
  produce evidence with the authoring between them collapsed, each step's standing after
  every operation, and each operation's path across client, API, supervisor, workbench,
  executor, and core.
- **Provenance** (`just provenance-recording <recording>`): for a sealed REE, each step's
  evidence at seal traced back through attempt, dispatch, and run to the request, with
  the verdict of every rule each link triggered.

## Workflow

1. Change behaviour here, in its own commit. Review it with `diff --base HEAD`.
2. `just generate-behaviour` regenerates `protocol/src/repo2ree_protocol/behaviour/machines.py`
   (`just check-conformance` fails while it is stale).
3. Implement. Owners change state where they already did and record each change through
   `repo2ree_protocol.behaviour.journal()`; `require_transition` enforces a machine
   in-process (today: Allocation, and settled Runs are never rewritten).
4. `just test-conformance` runs the scenario suite: the real owners and core in one process,
   with faults injected at boundaries. Every specified edge must be exercised by a scenario
   or listed in `UNEXERCISED` with a reason; the suite fails in both directions.
5. `just demo-gui` (or `just check-behaviour <recording>`) checks a real end-to-end run.

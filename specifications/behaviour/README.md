# Behaviour specification

This directory is the human-owned statement of how repo2ree behaves at runtime.
Implementation is checked against it: owners record what they do, Git witnesses
what the REE became, and `repo2ree_conformance` decides whether that evidence
conforms.

Review changes here carefully. Code that satisfies the checker does not need the
same line-by-line review; a wrong specification makes the checker approve wrong
code. The same holds for the checker that applies it (`conformance/`, with its tests and
the edges they excuse): a commit may change this directory or the checker, or runtime
code, not both (the `spec-isolation` pre-commit hook).

## Model

| File | Declares |
|---|---|
| `components.toml` | Components and the process each runs in. A process journal speaks for the components it hosts. |
| `entities/*.toml` | State machines. Each has exactly one **owner** component; nothing else changes its state. |
| `boundaries/*.toml` | Request/response exchanges between components, recorded by the sender. `cites` names records of the exchange and of the receiver's entity that name each other. |
| `invariants.toml` | Cross-entity rules, each in one fixed pattern. |

| Entity / boundary | Owner | Evidence |
|---|---|---|
| `Run` | api (`JsonRunStore`) | API process journal, reconciled against `runs/*/state.json` |
| `Allocation` | supervisor (`AllocationStore`) | API process journal, reconciled against `allocations.json` |
| `dispatch` | supervisor → workbench (`dispatch_action`) | API process journal |
| `Attempt` | core (`capture_command`) | the REE's Git history: each attempt record lists the phases it entered, in order, in capture commits and pending records |
| `Ree` | core | **witnessed** from Git: a transition per commit whose tree changed, `sealed` iff the committed `ree.json` carries a seal |
| `Step` | core | core's `audit()` before and after each author attempt, recorded in the capture commit |

Not yet specified: reviews (they have their own histories), workbench sessions,
uploads, read-only queries, the REE index and deposits, and the workbench's side
of `dispatch`.

## Evidence and order

- **Journals** (`BEHAVIOUR_JOURNAL_DIR`, one `<process>-<epoch>.ndjson` per process
  start) carry contiguous sequence numbers, so a lost record is a visible gap. A
  journal closed deliberately ends with `journal.closed`; one closed for good (the owner
  will not resume: a decommissioned deployment, the end of a test stack) carries
  `"final": true`. Only a final close gives "eventually" a horizon for an entity that
  outlives a restart.
- **Git** is core's journal. Facts that matter are read from Git itself where
  possible (tree changes, the seal), not from what the owner claims.
- **Stores** are the owners' persisted state, snapshotted after they stop. The
  `reconciliation` rule requires them to equal what the journals replay to, so a
  state change that bypassed journaling is a violation.

Order comes only from: positions within one source; epochs then positions within
one process's journals; and citations, where a record names another (a journal
record's position, a commit's hash) that it could only know once that record
existed. An `Attempt` cites the `dispatch` request that sent it, and the `result`
cites the commit that captured it; without the citation the evidence cannot order
the two, and the rule that needed the order is inconclusive. Wall-clock time is
never used, and neither is an assumption about where the receiver did its work.

## Recordings

A recording is a directory whose `manifest.json` lists each source it holds: its kind
(`journal`, `git`, `state`, `spans`), where it was collected from (`origin`, e.g. the
control plane it was fetched through), and whether collection succeeded. The system is
distributed, so nothing assumes one host; readers find evidence only through the manifest,
and a source listed as failed or missing makes the check inconclusive. `repo2ree_collect`
(`just collect-behaviour <control-plane> <dir> [ree…]`) gathers one through the control
plane alone: journals and persisted state from `/api/v1/behaviour`, REEs via `ree-archive`.

A deployment that shuts down for good (a test stack does) can instead export its owners'
journals and persisted state after they stopped (`repo2ree_collect --journal-dir`): taken
after the owners stopped, they carry no cut, and only they hold the journals' close, which
gives "eventually" its horizon. The e2e harness collects REE archives through the control
plane while it runs, then exports the owners once the stack stopped.

An REE's Git evidence is the archive the product downloads (`ree-archive`, the GUI's
*Download REE*). The archive checks out the seal and keeps the history it came from as
`refs/repo2ree/imports/<tip>/journal`; the checker reads that history.

A snapshot of a running system carries a **cut**: the journal positions read just before
and just after it was taken. Only what happened before the cut must be in it, so a record
missing from it is a violation only when the rule requires that record before a trigger
journaled before the cut; otherwise it is inconclusive. A store snapshot with a cut may
hold any state its journal reached around the cut. A source without a cut was taken after
its owners stopped and must match exactly.

## Patterns

| Pattern | Checked as |
|---|---|
| machine (per entity) | Transitions start where the last ended, follow declared edges, are recorded by the owner, carry declared facts, and never leave a terminal state. With `settles_before_close = true`, an entity must be terminal when its owner's journal closes; with `"final"`, when it closes for good. |
| exchange (per boundary) | Per key: one request, then at most one response or abandonment, never before the request, and not missing once the sender's journal closed. |
| `requires` | When the trigger occurs, the keyed entity reached one of the listed states (with facts) or the keyed message exists; with `order = "before"`, it happened before the trigger. An entity still open is violated when the evidence covers everything before the trigger, as a record never written is. |
| `response` | After the trigger, the entity eventually reaches one of the listed states: violated once its owner's journal closed in a way that settles it (see `settles_before_close`) and it had not; inconclusive while it still could. |
| `guard` | The triggering transition's facts satisfy a condition (for example: a receipt appears only through its own operation). |
| `excludes` | At the trigger, no entity of the given kind in the same partition is in the listed states. |
| reconciliation (implicit) | Persisted store state equals the journal replay. |

Triggers name target states (`to`), optionally source states (`from`, where
`(none)` means creation), and fact conditions (`where`). Conditions take a value,
`{ not = value }`, or `{ in = [values] }`; an absent fact never matches, and a fact recorded
as null is absent.

## Verdicts

- **violated**: complete evidence that covers the subject contradicts the specification.
- **inconclusive**: the evidence cannot decide: a journal gap, no source for the
  partition, an entity still in flight, events the evidence cannot order, journals
  written against another specification digest, or no behaviour at all.
- **passed**: every triggered rule held. A check where nothing triggered is inconclusive.

The CLI exits 0, 1, or 2. Checking is its own step on a collected recording: test runs and
demos only collect, so a test's outcome never depends on the checker, and a gate composes the two.

## Gate

`just behaviour-gate` runs the per-test tiers (`e2e-system`, `e2e-gui-instant`) on a clean
HEAD, checks every test's recording again with the checker in that tree, and accepts a test
only when it passed (or is a strict xfail) and its behaviour passed. A test may instead leave
open exactly the rules `conformance/expected-verdicts.toml` excuses for it, each with its
reason; the sets must match, so a fix that makes the test conform makes its excuse stale, and a
stale or unused excuse fails the gate. The excuses are part of the oracle, committed apart from
runtime code like the checker. When every test is accepted, the gate writes
`.validation-certificates/behaviour-ok`, binding the verdicts to HEAD's tree; `publish-gate`
requires it. `just judge-e2e [run…]` judges runs the same way without certifying anything.

## Views

`check -o DIR` writes `conformance.md`, `conformance.json`, and `conformance.html`:

- **System map**: processes ⊃ components ⊃ owned entities, boundaries, and invariants,
  drawn from this directory alone (`python -m repo2ree_conformance map`).
- **State machines** with each edge labelled by how often it was exercised; `0` is
  specified behaviour no evidence reached.
- **Specification diff**: `python -m repo2ree_conformance diff --base <ref>` draws
  added and removed edges, entities, invariants, and boundaries for review.

Views of a recording's evidence live in `repo2ree_traceview`, which draws the verifier's
artifact (`verification.json`: the evidence, replayed model, and verdicts) and never
verifies itself; OpenTelemetry spans are attached as context and never change a verdict.
Collect, check, and draw are separate steps, each on the previous one's artifact:
`just collect-behaviour` (or any e2e run) → `just check-behaviour` → the views.

- **Operation trace** (`just trace-behaviour [recording]`): setup, the operations that
  produce evidence with the authoring between them collapsed, each step's standing after
  every operation, and each operation's path across client, API, supervisor, workbench,
  executor, and core.
- **Provenance** (`just provenance-behaviour [recording]`): for a sealed REE, each step's
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
5. `just demo-gui` collects a recording of a real end-to-end run (`just collect-behaviour` does the
   same for any running deployment); `just check-behaviour [recording]` judges it, the newest by default.
6. Commit, then `just behaviour-gate`: the change is done when HEAD carries a behaviour receipt.

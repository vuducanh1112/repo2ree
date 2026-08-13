# Understanding the repo2ree Step Lifecycle

> Status: current (2026-07). Design rationale for
> [`core/operations/steps/`](../../../core/src/repo2ree_core/operations/steps/) and the
> handlers under [`core/operations/handlers/`](../../../core/src/repo2ree_core/operations/handlers/).
> The modules themselves document *what* each helper does; this page records *why*
> the shape is what it is.

repo2ree has two step lifecycles that mirror each other by design:

| | Author side | Review side |
|---|---|---|
| Module | `operations/steps/author.py` | `operations/steps/review.py` |
| Durable record | a **receipt** per step | one **attempt** record, updated per step |
| Question it answers | "what did this run consume and produce?" | "does the author's claim hold here?" |
| Descriptor | `RunnableStep` | `ReviewRunnableStep` |

They are kept symmetric on purpose: a discipline established on one side is
expected to appear on the other, and the review side was brought up to the
author side's standard in `914d4d8`.

## Why the ceremony is shared

A step handler is mostly ceremony around one script run — open the REE, digest
what the run is about to consume, run it, write the durable record binding the
two, and report a status that agrees with all three. That ceremony lives in the
`steps/` modules so the handlers can be about what makes them *different*.

Two specific things must not be duplicated:

- **The input slice.** It is the chain that makes a receipt auditable. Two
  spellings of it would be two chains, and an auditor could not tell which one
  a given receipt used.
- **The closing line.** The duration format string is centralised because it had
  already drifted once when four review handlers each spelled their own exit.

## The abstraction stops at the run

`RunnableStep` and `ReviewRunnableStep` both cover how a step *gets to* its run
and stop there. On the review side that is: join the attempt, prove the step
before it completed, prove the certified runtime is still the certified runtime,
resolve the author's runnable, run it.

What happens *afterwards* deliberately stays in the handlers. Activation and
experiment steps write different evidence documents, attach them to different
fields of the record, and reach their verdicts by different rules — one compares
nothing, the other diffs against the author's recorded run. A runner that owned
settlement too would need a callback carrying most of each handler's body.

The descriptors are also generic in the runnable they select, so a handler gets
back what it resolved rather than the widened `Runnable` base — an experiment
step needs the `name` and `output_paths` only an `Experiment` has.

## Nothing in `steps/` knows its callers

Not by name, and not by type. A step that needs to record something another does
not says so with a descriptor field — it brings its own receipt rather than
handing over a receipt *class* the shared module would have to interrogate.
Recognising a caller by the shape of its evidence is the same coupling as
recognising it by its operation string, and fails the same way when a third step
arrives.

## A review step ends exactly two ways

`ReviewStep` hands a handler its `stop` and its `settle` together, so the record,
the log line, and the span agree however the step came out. They are one object
because they are one obligation.

- **`stop`** — the step *could not run*: canceled, a precondition it cannot meet,
  a script that exited nonzero. It settles the step on the persisted record, says
  so in the log, and returns a result that agrees with both.
- **`settle`** — the step *ran to completion*, whatever the verdict. A build whose
  closure differs and a runtime that would not come up are both the review
  working correctly.

Routing a completed-but-unwelcome result through `stop` would put the attempt
into `failed` and conflate "the review could not run" with "the review has news".

`stop` and `settle` are closures over the step's identity (layout, key, timer,
log, noun) held as dataclass fields rather than methods, so a handler cannot call
them with a different identity than the one it started.

## Guards run before the step is marked running

`require_ree_baseline` and `require_review_record` both halt *before*
`begin_review_step`. A baseline or attempt nobody can read is a precondition
nobody can meet, so there is nothing to mark running and nothing to settle a halt
on.

The baseline read in particular was unguarded until `914d4d8`: a review command
against a damaged workbench raised straight out of the handler, past the
dispatcher (which does not catch), and out of the executor as a traceback with no
`ActionResult` at all — a shape upstream callers cannot read.

## Why `require_certified_runtime` is shared

Three things must hold before any step runs *inside* what the build left behind,
and they are the same three whichever step is asking: the attempt settled a basis
and a build receipt, its workspace is still there, and the runtime in that
workspace is byte-for-byte the one the build certified.

The last check is the reason this is shared rather than repeated. A re-run build
would otherwise leave an earlier step's verdict standing over a runtime that no
longer exists — and a verdict about bytes nobody can point to is worse than no
verdict, because it still reads as one.

## The caller protocol

Every `require_*` / `open_*` helper returns either the value or the
`ActionResult` to return unchanged:

```python
ree = require_ree_baseline(ree_layout, log=log)
if isinstance(ree, ActionResult):
    return ree
```

Helpers that only guard return `ActionResult | None` instead:

```python
halted = require_completed_step(started, "build", stop=stop, message="…")
if halted is not None:
    return halted
```

Every refusal has already settled the record and said why, so a caller never
decides how a halt is reported.

## See also

- [Concept reference](../reference/concepts.md) — Run Receipt, REE assessment, lifecycle states.
- [Component reference](../reference/components.md) — where `core` sits relative to the executor and the agent.

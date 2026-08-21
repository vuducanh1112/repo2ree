# Understanding the Review Evidence Model

> Status: current (2026-07). What a reviewer-side attempt actually certifies, and
> why each step certifies it that way. The code lives in
> [`core/evidence/review/`](../../../core/src/repo2ree_core/evidence/review/) and
> [`core/operations/handlers/review/`](../../../core/src/repo2ree_core/operations/handlers/review/).
> For the *shape* of a review step handler, see [step-lifecycle.md](step-lifecycle.md).

## The attempt is a parallel REE tree

A review attempt never writes into author evidence. It gets its own tree under
`review/<review_id>/` with its own `upstream/`, `overlay/`, and `workspace/`. The
author's overlay is **copied** into it — not referenced, not hard-linked —
because the merge writes into the attempt's workspace and a build script may
write beside itself.

The workspace the reviewer's steps run in is assembled by the same
`materialize` script the author's workbench runs, from source the attempt
acquired for itself.

## Verdict per step, and why it differs

What settles a verdict differs per step, because the certifiable property does.

| Step | Certifies by | Why not something stricter |
|---|---|---|
| **source** | SWHID identity | Nothing weaker is needed — source *is* reproducible bit for bit. |
| **build** | runtime digest, else SBOM closure | Container builds bake in timestamps, layer ordering, and base-image tags that move under a pinned name. Identical inputs routinely yield different bytes while installing exactly the same software. |
| **activation** | the reviewer's own probe | No author artifact exists to reproduce. The author's activation is a *precondition* of a credible baseline, not a baseline to diff against. |
| **experiments** | the author's verify script, re-run | A run that stamps a timestamp or draws a seed produces different bytes on every honest reproduction. The author already declared what counts as correct. |

Activation is recorded as an `ActivationOutcome` rather than a `Comparison`, so
the type itself keeps "this is a probe, not a diff" visible.

### The build ladder

Strongest first, in `compare_build_runtimes`:

1. **`identical`** — equal runtime digests. The build is bit-reproducible. Rare.
2. **`equivalent` / `different`** — the SBOM dependency closures decide, scanned
   off the runtime in hand and diffed against the author's recorded SBOM.
3. **`inconclusive`** — the closure could not be compared: no author SBOM, an
   unsupported artifact shape, a missing scanner, or a scan that yielded nothing.

`inconclusive` is deliberately not a pass. An absent baseline is not agreement,
and the verdict is a statement about the *evidence*, not about the build.

### The experiment ladder

Decided in this order, in `compare_experiment_results`:

1. **No verify script declared** → `inconclusive`. All that remains is "the run
   script exited 0", which for a script whose last act is to write a results file
   says only that something ran. A free verdict certifies nothing.
2. **The author never ran this experiment** → `inconclusive`. No baseline claim to
   have reproduced.
3. **The author criterion is unbound or changed** → `inconclusive`. A verify
   script with no author-receipt digest cannot be audited, and a different
   script answers a different question.
4. **The author's verify did not pass** → `inconclusive`. No accepted baseline
   claim exists to reproduce.
5. **Reviewer verify exited nonzero** → `different`. The author's own criterion, applied to
   the reviewer's results, rejected them. This is the step working.
6. **Reviewer verify exited 0** → `reproduced`, upgraded to `identical` when both sides
   recorded an output digest and the two agree.

An output digest mismatch never downgrades a passing verify. A criterion digest
mismatch does: the reviewer did not run the test that established the baseline.

The cost of this design is that a verdict is worth exactly as much as the script
that granted it, and verify scripts range from a tolerance check against
reference values to `test -f results.csv`. Two things keep that honest rather
than hidden: no verify script is `inconclusive` rather than a free pass, and the
comparison records both the author's expected verify-script **digest** and the
reviewer's observed digest, and grants a reproduction verdict only when they
agree.

## Activation carries two things a comparison would have carried

Activation has no comparison, so:

- **Basis is inherited, not chosen.** Activation runs in the workspace the build
  left behind and deliberately cannot tell whether the runtime there was rebuilt
  or unpacked — that indifference is what lets the author's scripts run unchanged
  on either basis. It adopts the weakest basis the attempt has settled: passing on
  a shipped artifact says that artifact is inhabitable, never that the world still
  produces one.
- **Identity is checked, not assumed.** The probe is bound to the runtime digest
  the build step recorded, so an attempt whose build has since been re-run cannot
  leave a pass attached to a runtime that no longer exists. This mirrors the
  author-side aggregate assessment.

A runtime that does not come up **completes** the step with a `failed` verdict
rather than failing the step — the reviewer's machine did exactly its job. Only
the conditions that stop it probing at all (reclaimed workspace, no activation
script, stale runtime) fail the step.

Activation must have *passed*, not merely completed, before experiments run.
Every experiment inside a runtime that would not come up fails for one reason
that has nothing to do with the experiments, and a wall of `different` verdicts
would bury the single fact that explains them all.

## Evidence bases: what an agreement is worth

Every comparison carries an `EvidenceBasis` independent of its verdict:

- **`independent`** — the reviewer rebuilt/refetched from their own acquisition.
  Agreement here is a reproduction.
- **`bundled`** — the reviewer certified the artifact the REE already ships.
  Nothing was reproduced; the same scan and the same closure diff ran, but
  against the author's own bytes.

`bundled` exists because the alternative, for a baseline whose build cannot run
here — no Docker, wrong architecture, no network — is no verdict at all. It is an
**integrity check**, and the basis is recorded on the comparison so it can never
be read as a reproduction.

The verdict ladder is **basis-blind on purpose**: a shipped runtime that does not
match the author's own receipt still comes back `different`. What agreement is
worth is carried by the basis, not by the verdict.

`auto` picks `independent` when a build recipe exists and falls back to
`bundled`. It refuses only when the baseline offers neither.

## Both bases leave the same workspace

Source materialized from the attempt's own acquisition, with a runtime beside it
at the path the recipe expects. Only *how* the runtime got there differs — built
here, or copied in from the bundle — because activation and the experiments run
*in* that workspace and cannot tell the difference.

## Cancel is not a verdict

An abandoned scan says nothing about the runtime. Cancellation halts the step
rather than settling `inconclusive` over it — "nobody asked the question" must
not be recorded as "the evidence could not answer it", because the second reads
as a finding about the build.

## Where the author's runtime digest comes from

The build receipt binds the declared runtime path to the digest it produced.
Review compares against that digest only while the REE still declares the same
path; a missing build receipt or a changed path leaves the digest tier without
an author baseline.

## See also

- [step-lifecycle.md](step-lifecycle.md) — the handler shape these steps share.
- [Concept reference](../reference/concepts.md) — Run Receipt, Repro Label, fidelity tiers.

# repo2ree — Toward a Truly REE Service

A feature analysis grounded in the current codebase. repo2ree today is an
excellent **environment-capture** tool. Becoming a true *Reusable Execution
Environment* service requires three more pillars: a way to **verify
reproduction**, a way to **reuse** an REE, and a way to **trust** one you
didn't build.

## The core gap: outputs are not modeled

Reproducibility = same inputs + same environment → **same outputs**.

`ReeSpec` (`frontend/src/core/ree/ReeSpec.ts`) captures inputs and environment —
source, runtime, build/activation scripts, SBOM, hardware BOM, and experiment
*commands* — but has **no concept of an expected output**. `ReeExperiment` is
just `{ name, description, command }`; there is nowhere to record "this command
should produce *this* result."

Consequence: "reproduces the same outputs" is currently unfalsifiable. The
evaluate threat report can only score *how well the environment is pinned*,
never *whether the REE actually reproduces*.

## Pillar 1 — Outputs & reproduction verification (keystone)

The highest-leverage direction. Without it, the existing Experiments and Evaluate
pages have no real meaning.

- Expected-output capture per experiment (artifact paths, hashes, or a result
  manifest).
- A **re-run → diff against baseline** loop. This is what makes wiring up
  Experiments-run worthwhile — otherwise "run" only checks "did it exit 0."
- A green/red "this REE reproduced" verdict, distinct from "this REE is
  well-specified."

Frontend-visible today: the **Results** and **Traces** panes on the Experiments
detail view are literal placeholders
(`frontend/src/shell/ui/app-shell/pages/experiments/ExperimentsPageSections.tsx`),
and the **Run** button is hard-disabled (`title="Run is not yet wired up"`).
Note: a full implementation also needs a backend run endpoint for experiments —
none exists today (build-runtime / activation-test / sbom / evaluate do).

## Pillar 2 — Reuse (the consumer side)

The app is overwhelmingly **author-side** (build & seal). "Reusable" implies a
second persona: someone who finds an REE and runs it.

- **REE library / registry**: list, search, and filter REEs (by keyword,
  runtime, reproducibility standing). Today there is only the landing loader.
- **Versioning & diff**: an REE evolves as dependencies drift. Need real
  versions and a diff between them — not the single free-text `version` string
  inside `catalog_metadata`.
- **Fork / re-instantiate**: take an existing REE as a starting point.

## Pillar 3 — Trust over time

A service implies REEs that outlive their authors.

- **Drift detection**: dependencies rot. Dependencies are already extracted via
  Renovate — the natural extension is *scheduled re-build + re-run* with an alert
  when a previously-reproducing REE stops. A background/scheduled job fits here.
- **Shareable trust artifact**: a consumer-facing "reproducibility report card" /
  badge that can be relied on without re-running. The evaluate report is the
  seed, but it is currently inward-facing.

## Lower-priority / ecosystem

- **Standard export**: RO-Crate, Nix flake, OCI image, CodeMeta — interop with
  the broader reproducibility ecosystem.
- **Hardware matching**: HBOM is descriptive only today; actually
  provisioning/matching captured hardware (especially GPU) is what makes
  hardware-sensitive science reproduce.
- **Multi-user**: accounts, ownership, permissions (appears single-user/demo
  now).

## Recommendation

Build toward an **outputs/result model and a reproduction-diff loop** first. It
is the missing half of the product promise, it is already frontend-visible
(the Experiments Results/Traces placeholders are waiting for it), and it
converts everything already built from "well-described environment" into
"verified reproduction."

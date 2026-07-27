# repo2ree — Toward a Truly REE Service

A feature analysis grounded in the current codebase. repo2ree now has the
outline of an REE builder: source acquisition, build/runtime scripts, SBOM/HBOM
generation, dependency evaluation, experiment runs, author-provided verify scripts,
and sealing. Becoming a true *Reusable Execution Environment* service still requires
three pillars: stronger **verification**, a consumer-side **reuse** loop, and
durable **trust over time**.

## The core gap: receipts are not yet durable claims

Reproducibility = same inputs + same environment → **same outputs**.

`ReeSpec` (`frontend/src/core/ree/ReeSpec.ts`) now captures a runnable
`verify_script` and declared `output_paths`, and the backend can run experiments
through the typed command envelope
(`api/src/repo2ree_api/authoring/stages.py`,
`core/src/repo2ree_core/experiment/run.py`). That is the right foundation.

The remaining gap is that an experiment run is still mostly an execution result,
not a durable **Run Receipt** with content-addressed inputs, output contracts,
predecessor lineage, archive identity, and reviewer-facing diffs. The product
can execute author-owned checks, but it has not yet turned those checks into the
citable claim object promised by the concept docs.

## Pillar 1 — Outputs & reproduction verification (keystone)

The highest-leverage direction. The code has the first loop; now make it a
publication-grade loop.

- Promote experiment run results into immutable Run Receipts.
- Add predecessor links so reviewer runs point at author runs.
- Preserve captured files/stdout/stderr as content-addressed evidence.
- Surface a **re-run → diff against baseline** loop in the UI, not just a
  pass/fail run status.
- A green/red "this rerun matched the author baseline" verdict, distinct from
  both "this author run validated" and "this REE has strong evidence."

Frontend-visible today: experiment run actions exist, and verify scripts can
produce pass/fail verdicts plus named check rows. The missing surface is a
durable receipt view:
baseline vs. rerun, predecessor, captured artifacts, and claim-level comparison
in one object a reviewer can cite.

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

- **Sealed identity**: promote sealing from a UI action into a durable Seal
  Manifest with `ree_digest`, detached signatures, timestamp evidence, and
  archive-binding metadata.
- **Drift detection**: dependencies rot. Dependencies are already extracted by
  the first-party manifest parsers — the natural extension is *scheduled
  re-build + re-run* with an alert when a previously-reproducing REE stops. A
  background/scheduled job fits here.
- **Shareable trust artifact**: a consumer-facing "reproducibility report card" /
  badge that can be relied on without re-running. The evaluate report and
  experiment verdicts are the seed, but they are still inward-facing.

## Lower-priority / ecosystem

- **Standard export**: RO-Crate, Nix flake, OCI image, CodeMeta — interop with
  the broader reproducibility ecosystem.
- **Hardware matching**: HBOM is descriptive only today; actually
  provisioning/matching captured hardware (especially GPU) is what makes
  hardware-sensitive science reproduce.
- **Multi-user**: accounts, ownership, permissions (appears single-user/demo
  now).

## Recommendation

Build toward **durable Run Receipts and a reproduction-diff loop** first. The
verify-script model is now present; the product move is to make each run
citable, comparable, and depositable.

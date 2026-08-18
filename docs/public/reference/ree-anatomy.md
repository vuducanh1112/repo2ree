# Anatomy of an REE

An REE is a directory with one document at its root. The directory holds the
bytes — source, recipe files, produced evidence — and the document,
`ree.json`, records what the REE declares and what running it produced. A
published bundle is that same directory, packed.

This page is the layout and schema reference. For why the object is shaped this
way, see [What is an REE?](../explanation/what-is-an-ree.md).

## Directory layout

Every REE has the same tree, whether it sits in repo2ree's storage on the host
or is mounted at `/ree` inside its workbench container:

```text
ree.json                     the REE document
sealed.zip                   immutable sealed archive, written by Seal
snapshot.tar.gz              frozen source archive
acquire_source.sh            fills upstream/ from an origin or the snapshot
materialize_workspace.sh     derives workspace/ from upstream/ + overlay/
upstream/                    extracted snapshot, treated as read-only
overlay/                     authored and tool-generated recipe files
artifacts/                   produced evidence
  sbom.json                  software bill of materials
  reproducibility-report.json   the Evaluate report
workspace/                   materialized view: upstream + overlay
results/<name>/              captured outputs, one directory per experiment
runs/                        per-action logs and receipt history
reviews/<review-id>/         one independent review attempt
upload-staging/              staging area for in-flight source uploads
```

Three of those directories carry the whole model:

| Directory | Role |
|---|---|
| `upstream/` | Source of truth. The project as acquired, never edited. |
| `overlay/` | Source of truth. Everything repo2ree adds beside the project. |
| `workspace/` | Derived. Rebuilt from the other two at any time. |

Because `workspace/` is derived, discarding it loses nothing. Because
`upstream/` is never written to, the recipe stays separable from the project it
describes — which is what lets a reviewer rebuild from the original source
rather than from the author's working tree.

A review attempt under `reviews/<review-id>/` is itself an REE root: it carries
its own `upstream/`, `overlay/`, `workspace/`, and `artifacts/` under the same
names, so the same acquire and materialize scripts run there unchanged. It adds
`review.json`, `receipts/`, and `comparisons/` — the attempt's own evidence,
kept beside the author's rather than merged into it.

### Reserved script paths

repo2ree's own scripts live in one namespace inside the overlay, `ree-scripts/`,
so they cannot collide with or shadow a project file of the same name when
upstream and overlay merge into the workspace:

| Path | Purpose |
|---|---|
| `ree-scripts/build_script.sh` | Builds the runtime artifact. Seeded on creation. |
| `ree-scripts/activation.sh` | Proves the built runtime can be entered. Seeded on creation. |
| `ree-scripts/activation.verify.sh` | Optional check on activation. Declaring one is an authoring act. |
| `ree-scripts/experiments/<slug>.sh` | One experiment's run script. |
| `ree-scripts/experiments/<slug>.verify.sh` | That experiment's optional check. |

Experiment slugs derive from the experiment name, with whitespace collapsed to
hyphens. The document rejects a script path that does not match the name it
belongs to, so the two cannot drift apart.

## The `ree.json` document

The document has two top-level keys:

```json
{
  "subject": { "schema_version": 1, "definition": {}, "receipts": {}, "contents": {} },
  "seal": null
}
```

`subject` is everything the seal covers. `seal` is the freeze over it, absent
while the REE is a draft. An REE with a seal is **sealed**; without one it is a
**draft**.

| Key | Meaning |
|---|---|
| `subject.schema_version` | Document version. Currently `1`. |
| `subject.definition` | What the author declares: identity, source, recipes, experiments. |
| `subject.receipts` | What running it produced. One entry per completed operation. |
| `subject.contents` | The bundle inventory: every packed path with its digest and size. |
| `seal` | Timestamp, digest over the subject, and an optional signature. |

Unknown keys are rejected everywhere. A document that carries a field this
schema does not define does not load.

### `definition`

| Field | Type | Notes |
|---|---|---|
| `name` | string | The REE's name. |
| `catalog` | object | `description`, `version`, `website`, `keywords`, `contributors`, `corresponding_author_identifier`. |
| `source` | object or null | `origin_url`, `source_type`, `requested_ref`. |
| `build_runtime` | object or null | Build script path, digest, size, and `runtime_path` — where the build must leave its artifact. |
| `test_activation` | object or null | Activation run script and optional verify script, each with digest and size. |
| `hardware` | object or null | HBOM: CPU, GPU, memory, storage, and network entries. |
| `experiments` | array | One entry per experiment, each with scripts, digests, and `output_paths`. |

`source_type` is one of `git`, `hg`, `svn`, `cvs`, `bzr`, `tarball`, or `zip`.
Experiment names and their derived slugs must both be unique, and an
experiment's `output_paths` must not repeat.

Verification is all-or-nothing: a verify script's path, digest, and size are
present together or not at all. `runtime_path` is optional only because a fresh
REE is seeded with a build script before it has a source; the build step refuses
to run until it is declared.

### `receipts`

A receipt records one operation that **succeeded**. Failed and cancelled
attempts are run records under `runs/`, not receipts — a value here is evidence
that the named operation completed.

| Key | Operation |
|---|---|
| `source` | `acquire_source` |
| `evaluation` | `evaluate_reproducibility` |
| `hardware_observation` | `observe_hardware` |
| `build` | `build_runtime` |
| `sbom` | `generate_sbom` |
| `sbom_cross_check` | `cross_check_sbom` |
| `test_activation` | `test_activation` |
| `experiments` | `run_experiment`, keyed by experiment name |

Every receipt shares one envelope — `schema_version`, `run_id`, `started_at`,
`finished_at`, `duration_ms`, `recorded_at` — and adds fields specific to its
operation. Timestamps are UTC, ISO-8601 with a trailing `Z`, and must be
ordered: a run cannot finish before it starts, or be recorded before it
finishes.

What each receipt adds, in brief:

- **`acquire_source`** — the resolved revision, an observed SWHID when the
  origin has one, and the digest of the frozen snapshot.
- **`evaluate_reproducibility`** — the independent dependency, environment, and
  machine levels, the counts behind them, and the analyzer version.
- **`build_runtime`** — the build script's digest, whether the workspace had
  drifted, and the digest of the runtime actually produced.
- **`generate_sbom`** — the digest of the scanned runtime, the SBOM's digest and
  format, and the scanning tool's version.
- **`cross_check_sbom`** — how the declared dependencies and the observed ones
  reconciled: matches, version mismatches, and undeclared packages.
- **`test_activation`** and **`run_experiment`** — script digests and exit
  codes, which can only be `0`; an experiment also records a digest over its
  declared outputs.

Digests appear throughout in `sha256:<hex>` form. They are what makes a receipt
checkable later: the REE assessment compares the digests a receipt recorded
against the tree as it now stands, and reports evidence as current or stale
without ever storing that judgment.

### `contents` and `seal`

`contents.entries` is the bundle inventory — one `{path, digest, size}` per
packed file, sorted by path, with no duplicates. On a draft it describes
whatever the last bundling saw, and any edit since makes it a description of a
bundle that no longer exists; nothing reads it as a claim about a draft.

Sealing fixes the inventory and the bytes together. `seal` records `sealed_at`,
a `ree_digest` computed canonically over the entire subject, and an optional
detached `signature`. A document whose `ree_digest` does not match its subject
will not load — the seal cannot outlive an edit.

## Bundle layout

A published bundle mirrors the tree above under a single `ree/` prefix, plus two
top-level files that let a reader reproduce the work without repo2ree installed:

```text
run.sh                        one-click reproducer
REPRODUCING.md                human instructions
ree/ree.json                  the same document the workbench keeps
ree/snapshot.tar.gz           frozen source archive
ree/acquire_source.sh
ree/materialize_workspace.sh
ree/overlay/...               recipe files
ree/artifacts/...             runtime, SBOM, and other produced evidence
ree/results/<name>/           author result baselines, for sealed experiments
```

`upstream/` is not packed: its contents are already in `snapshot.tar.gz`.
`workspace/` is not packed either — `run.sh` materializes it on extract, by
calling the same two scripts the workbench calls.

The `ree/` prefix is the REE root's own name by intent. Unpacking a bundle
produces a directory that *is* an REE root, carrying the manifest it will keep
under the name it already has. Nothing is renamed or copied across on load, and
the same scripts mean the same thing on both sides.

These entry paths are a format promise. They appear in every bundle ever
published, and a reader holding a year-old one resolves them literally.

## Example

A draft with a source acquired, recipes declared, and one experiment defined.
Digests are abbreviated here; real ones carry the full 64 hex characters.

```json
{
  "subject": {
    "schema_version": 1,
    "definition": {
      "name": "glacier-flow-model",
      "catalog": {
        "description": "Ice-sheet flow simulation from the 2026 EGU paper.",
        "version": "1.0.0",
        "website": "https://example.org/glacier-flow",
        "keywords": ["glaciology", "simulation"],
        "contributors": [
          {
            "identifier": "https://orcid.org/0000-0002-1825-0097",
            "name": "A. Researcher",
            "affiliation_name": "Example University",
            "affiliation_identifier": ""
          }
        ],
        "corresponding_author_identifier": "https://orcid.org/0000-0002-1825-0097"
      },
      "source": {
        "origin_url": "https://github.com/example/glacier-flow",
        "source_type": "git",
        "requested_ref": "v1.0.0"
      },
      "build_runtime": {
        "build_runtime_script_path": "ree-scripts/build_script.sh",
        "build_runtime_script_digest": "sha256:1f0c…",
        "build_runtime_script_size": 412,
        "runtime_path": "dist/runtime.tar"
      },
      "test_activation": {
        "run_script_path": "ree-scripts/activation.sh",
        "run_script_digest": "sha256:2a3b…",
        "run_script_size": 180,
        "verify_script_path": null,
        "verify_script_digest": null,
        "verify_script_size": null
      },
      "hardware": null,
      "experiments": [
        {
          "name": "figure-3",
          "run_script_path": "ree-scripts/experiments/figure-3.sh",
          "run_script_digest": "sha256:4c5d…",
          "run_script_size": 96,
          "verify_script_path": "ree-scripts/experiments/figure-3.verify.sh",
          "verify_script_digest": "sha256:6e7f…",
          "verify_script_size": 64,
          "output_paths": ["out/figure-3.png"]
        }
      ]
    },
    "receipts": {
      "source": {
        "schema_version": 1,
        "run_id": "r1",
        "started_at": "2026-08-17T09:00:00Z",
        "finished_at": "2026-08-17T09:00:12Z",
        "duration_ms": 12000,
        "recorded_at": "2026-08-17T09:00:12Z",
        "operation": "acquire_source",
        "origin_url": "https://github.com/example/glacier-flow",
        "source_type": "git",
        "requested_ref": "v1.0.0",
        "resolved_revision": "9f8e7d6c",
        "observed_swhid": "swh:1:rev:9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c",
        "snapshot_digest": "sha256:aabb…"
      },
      "evaluation": null,
      "hardware_observation": null,
      "build": null,
      "sbom": null,
      "sbom_cross_check": null,
      "test_activation": null,
      "experiments": {}
    },
    "contents": { "entries": [] }
  },
  "seal": null
}
```

Sealing this REE would fill `contents.entries` with the packed inventory and
replace `"seal": null` with a `sealed_at`, a `ree_digest` over everything
above, and — under the target design — a detached signature.

# How to archive and share an REE

Archive is the workflow that turns a working REE into something another person,
venue, or repository can keep.

## Current flow

1. Build and inspect the REE.
2. Generate software and hardware evidence.
3. Test activation.
4. Add archive identifiers or destination metadata.
5. Seal the REE.
6. Download the sealed ZIP bundle.
7. Deposit or share the bundle through the appropriate repository process.

The current prototype supports sealing and sealed bundle download. It also has
archive-oriented fields and UI for Software Heritage, Zenodo, and Dataverse.
Live external deposit adapters are planned work.

## Reproduce from the bundle

The sealed ZIP includes `run.sh` and `REPRODUCING.md` beside the `ree/` tree. A
recipient can run the build and experiments without installing repo2ree. The
tree holds the frozen source snapshot, author overlay, and sealed build
artifacts. `run.sh` reconstructs the workspace from them.

After extracting the ZIP, from that folder:

```shell
sh run.sh all                      # reproduce everything end-to-end (one click)
sh run.sh acquire-source           # extract/fetch the source (verify SWHID if able)
sh run.sh materialize-workspace    # assemble a clean workspace = source + overlay
sh run.sh build-runtime            # (re)build the runtime from the author's script
sh run.sh test-activation          # prove the runtime is inhabitable
sh run.sh experiment <name>        # run a named experiment
```

`run.sh` exposes the same reproduction commands as the in-workbench
`repo2ree-exec` CLI. The CLI also provides authoring commands.

`materialize-workspace` assembles `ree/workspace/` from the acquired source and
author overlay. It resets the workspace before each run. If the bundle includes
a runtime artifact (Replay tier or higher), `test-activation` and `experiment`
reuse it and skip the build. Otherwise, they build it first.

For a sourceless Cite-tier bundle, `acquire-source` fetches the origin and checks
the recorded SWHID when the `swh` tool is available. A missing `swh` tool
produces a warning, not a failure.

The host needs a POSIX shell, `tar`, and the runtime used by the author's
scripts—usually Docker.

## Why Seal comes first

Archive should preserve a stable object, not a mutable workspace. Seal is the
freeze point. Once sealed, the bundle can be downloaded and attached to an
archive record or institutional workflow.

The current seal binds a canonical REE subject and bundle inventory to
`ree_digest`. Detached signatures, timestamp evidence, digest migration, and
archive binding metadata remain target design.

## Archive tiers

repo2ree uses three archive tiers in its design:

| Tier | Public meaning |
|---|---|
| Cite | Preserve declarations, source pointers, labels, and run evidence. |
| Replay | Cite plus a runnable runtime artifact. |
| Rebuild | Replay plus enough dependency closure to rebuild after upstreams drift. |

The recommended default for most paper artifacts is Replay: preserve enough to
run the artifact later without requiring full dependency-closure capture.

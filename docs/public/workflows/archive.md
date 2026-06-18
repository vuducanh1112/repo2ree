# Archive and Share

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

## Why Seal comes first

Archive should preserve a stable object, not a mutable workspace. Seal is the
freeze point. Once sealed, the bundle can be downloaded and attached to an
archive record or institutional workflow.

The target design makes this stronger with a canonical Seal Manifest,
`ree_digest`, detached signatures, timestamp evidence, and archive binding
metadata. That target lifecycle is described in
[sealing.md](../../research/sealing.md).

## Archive tiers

repo2ree uses three archive tiers in its design:

| Tier | Public meaning |
|---|---|
| Cite | Preserve declarations, source pointers, labels, and run evidence. |
| Replay | Cite plus a runnable runtime artifact. |
| Rebuild | Replay plus enough dependency closure to rebuild after upstreams drift. |

The recommended default for most paper artifacts is Replay: preserve enough to
run the artifact later without requiring full dependency-closure capture.

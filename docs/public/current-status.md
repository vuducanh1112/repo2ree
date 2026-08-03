# Current status

repo2ree is an active prototype. The current app can create and manage an REE
workspace backed by an isolated workbench, while the long-term docs describe a
broader service around durable receipts, signatures, runners, and archive
adapters.

## Implemented in the current prototype

- Create an REE workspace backed by a per-REE Docker workbench.
- Acquire source from a URL or uploaded archive.
- Keep source separate from repo2ree's overlay and workspace state.
- Edit metadata, runtime instructions, activation scripts, hardware context,
  and experiment declarations.
- Evaluate source-repository declarations, reproducibility risks, and dependency evidence.
- Build a runtime from the declared build script.
- Generate SBOM and HBOM evidence.
- Test that a built runtime activates.
- Run experiment commands and validate results with author-provided verify scripts.
- Derive a per-step REE assessment from its definition, inline receipts, and
  bundle contents; this is evidence state, not a reproduction verdict.
- Seal the current REE state and download a sealed ZIP bundle.
- Track archive-oriented metadata such as SWHID, Zenodo DOI, and Dataverse DOI.

## Partially implemented or target design

- Run Receipts are the target public object for one execution. The current code
  has run records, logs, verify-script verdicts, and artifacts, but not yet
  a durable, citable receipt format with predecessor lineage.
- Verify is the target reviewer/reader workflow. The current app can re-run
  experiment commands and run their verify scripts; the full verification
  receipt and claim-level diff loop is still future work.
- Seal currently freezes a downloadable REE bundle. The target design adds a
  canonical Seal Manifest, stable `ree_digest`, detached signatures, timestamp
  evidence, and archive binding metadata.
- Archive support currently prepares and records archive metadata. Live deposit
  adapters for external repositories are planned work.
- Remote runners, institutional execution clients, and peer rebuilders are
  architectural targets, not required for the local prototype.

## Current execution model

The current demo uses Docker. The API provisions a workbench for each REE and
dispatches typed commands into that workbench. The long-term architecture keeps
that control-plane/execution-plane split but can move the workbench from local
Docker to stronger VM-backed or institution-owned runner deployments.

For local setup, see the [engineering deployment guide](../engineering/deployment.md).

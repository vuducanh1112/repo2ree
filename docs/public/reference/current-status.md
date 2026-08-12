# Current Capability Status

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
- Reproduce source, runtime builds, activation, and experiments in isolated
  review-attempt workspaces, keeping author evidence unchanged.
- Compare reviewer evidence with the author baseline: source identity, runtime
  digest or SBOM closure, activation outcome, and experiment verify/output evidence.
- Persist typed author and reviewer operation receipts and expose review verdicts
  in the API and GUI.
- Derive a per-step REE assessment from its definition, inline receipts, and
  bundle contents; this is evidence state, not a reproduction verdict.
- Seal the current REE state and download a sealed ZIP bundle.
- Give a sealed REE a canonical `ree_digest`, bind that digest to its bundle
  inventory, and retain a durable index entry after sealing.
- Track archive-oriented metadata such as SWHID, Zenodo DOI, and Dataverse DOI.

## Partially implemented or target design

- Successful author and reviewer operations already produce immutable typed
  receipts. They are durable inside the REE or review attempt, but they are not
  yet independently citable objects with predecessor lineage, signatures, or a
  deposit format of their own.
- Verify is implemented as a reviewer lifecycle over source, build, activation,
  and experiments. The remaining target work is portable/citable verification
  artifacts, explicit receipt-to-receipt predecessor links, and signing or
  depositing a review independently of its workbench.
- Seal currently creates a stable `ree_digest` over the canonical REE subject,
  records the bundle inventory, writes an immutable ZIP, and indexes the seal.
  Detached signatures, timestamp evidence, digest-migration attestations, and
  archive-issued binding records remain target work.
- Archive support currently prepares and records archive metadata. Live deposit
  adapters for external repositories are planned work.
- Remote runners, institutional execution clients, and peer rebuilders are
  architectural targets, not required for the local prototype.

## Current execution model

The current demo uses Docker. The API asks a connected agent to provision a
workbench for each REE, then dispatches typed commands through that agent. The
agent alone owns the Docker socket and container runtime. The long-term
architecture keeps that control-plane/execution-plane split but can move the
workbench to stronger VM-backed or institution-owned runner deployments.

Deployment and local-development instructions belong to the engineering
documentation in the source repository, not this end-user website.

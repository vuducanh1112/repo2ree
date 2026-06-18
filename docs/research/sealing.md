# repo2ree - Sealing and Long-Term Signatures

> **Status: proposed / feature-space.** Sealing is the lifecycle step that turns
> a mutable REE into a content-identified object. Signing is a separate,
> append-only layer of claims about that sealed object.

## Core idea

Sealing answers:

```text
Which exact REE is this?
```

Signing answers:

```text
Who claims what about this REE, when, under which policy?
```

Archive answers:

```text
Where can this sealed REE and its evidence be retrieved later?
```

Do not blur these. A sealed REE is immutable and identifiable. It is not
automatically trusted, reproducible, or archived.

## What sealing produces

Seal creates a canonical **Seal Manifest** and computes its digest:

```text
ree_digest = sha256(canonical_seal_manifest)
```

The manifest should be canonical JSON or CBOR with stable ordering. It should
hash a Merkle inventory of REE contents, not a zip or tar file whose timestamps,
file order, or compression settings may drift.

Minimum contents:

| Field | Meaning |
|---|---|
| `source` | SWHID when available, plus source tree digest or snapshot digest |
| `overlay_digest` | Digest of repo2ree declarations, generated recipes, and experiment specs |
| `runtime_digest` | OCI image descriptor or runtime artifact digest, for Replay+ |
| `dependency_archive_digest` | Closure digest, for Rebuild |
| `receipts` | Digests of Run Receipts and verification lineage |
| `label_digest` | Digest of the Repro Label snapshot |
| `bundle_tier` | Cite, Replay, or Rebuild |
| `created_at` | Seal creation time, informational only |
| `algorithms` | Hash algorithms used, initially `sha256` |

The digest is over the manifest without signatures. Signatures live beside the
sealed content and refer to `ree_digest`.

## Lifecycle

| State | Meaning | Mutation rule |
|---|---|---|
| Draft | Source, overlay, runs, or metadata may still change. | Edits allowed |
| Archive-ready | Source has stable identity; overlay and receipts are ready to freeze. | Edits allowed |
| Sealed | Seal Manifest and `ree_digest` exist. | Edits create a new seal |
| Deposited | Sealed bundle is exported/deposited and identifiers are recorded. | New deposit version or external attestation |

Signing is not a separate lifecycle state because signatures are plural and
append-only. An author, executor, reviewer, institution, and archive can all
sign different claims over the same `ree_digest`.

## Why sign at all?

A digest only proves content identity: these bytes are exactly these bytes. A
signature adds an accountable claim about that identity.

Core use cases:

| Signature | Claim |
|---|---|
| Author approval | "This sealed REE is the artifact for my paper/result." |
| Executor attestation | "repo2ree produced this runtime or run from this action in this workbench." |
| Reviewer verification | "I re-derived this receipt from that predecessor under this policy." |
| Archive binding | "This DOI/PID deposit contains or references this `ree_digest`." |
| Venue or institution acceptance | "This artifact passed this review/deposit policy." |
| Dependency rebuild | "This REE rebuilt offline from the captured dependency closure." |
| Digest migration | "This old digest and new digest name the same sealed manifest." |
| Correction or withdrawal | "This earlier artifact is superseded, corrected, or should not be used." |

The most important v1 signature is author approval. Without it, repo2ree can say
"a sealed REE exists," but not "the author intended this to stand for the
paper."

## Signature claims

A signature should bind a role and a claim to the sealed digest. It should not
mean "this will reproduce forever." Useful claims include:

| Signer | Claim |
|---|---|
| Author | "I approve this sealed REE as the artifact for this paper/result." |
| Executor | "This runtime/run was produced by this workbench/action." |
| Reviewer | "I re-derived these receipts from this predecessor." |
| Institution or venue | "This artifact passed this review/deposit policy." |
| Archive adapter | "This DOI/PID deposit contains or references this digest." |
| Rebuilder | "This REE rebuilt from the captured closure without live upstreams." |

Signature envelopes should include:

```text
subject_digest: sha256:...
claim_type: author_approval | executor_attestation | reviewer_verification | archive_binding | policy_acceptance | dependency_rebuild | digest_migration | correction
signer_identity: ...
signer_role: ...
signed_at: ...
policy: ...
signature: ...
verification_material: ...
```

DSSE/in-toto-style envelopes are a good fit because they sign typed statements,
not raw bytes. Sigstore, GPG, SSH signing, institutional certificates, or
hardware keys can all be adapters if they produce the same envelope shape.

## Signing verification runs

Verification runs should be signed too. A verification is not just an internal
status check; it is a scholarly object that says one actor re-derived another
actor's claim.

A verification run should produce a receipt like:

```text
verification_receipt_digest
predecessor_receipt_digest
ree_digest
verification_action_digest
comparison_contracts
outputs_checked
outputs_unchecked
verdict: pass | fail | partial | inconclusive
verifier_identity
executor_identity
timestamp
```

The verifier can then sign:

```text
I, <verifier>, re-derived receipt X from predecessor Y
against sealed REE Z under comparison policy P.
The result was pass | fail | partial | inconclusive.
```

This makes verification cumulative:

```text
author seals REE
author signs author approval
executor signs build/run attestations
reviewer runs Verify
reviewer signs verification receipt
venue signs acceptance policy
archive signs/binds DOI/PID deposit
```

The chain does not make the result true forever. It makes the evidence durable,
inspectable, and attributable.

## Long-term archival requirements

Long-term signature validation needs more than a detached signature file.

Preserve:

- the signature envelope;
- public key or certificate chain;
- timestamp evidence, such as RFC 3161 or transparency-log inclusion;
- revocation status or verification bundle at signing time;
- verification policy and software version;
- signer role and identity context;
- digest algorithm identifiers.

This matters because keys expire, people leave institutions, certificate
authorities rotate, and algorithms age. A verifier in 2036 should be able to
distinguish:

- the signature was valid when made;
- the signer identity can still be resolved;
- the key was later revoked;
- the hash algorithm is now deprecated;
- the archive still contains the sealed object.

## Algorithm agility

`sha256` is a practical v1 default, but the manifest should use multihash-style
algorithm identifiers. If a hash weakens, do not mutate the sealed object.
Instead add a **digest migration attestation**:

```text
old_digest: sha256:...
new_digest: sha512:...
same_manifest: true
signed_at: ...
timestamp_evidence: ...
```

The archive can then preserve continuity from old identifiers to new ones
without rewriting historical receipts.

## Archive interaction

Archive should deposit the Seal Manifest with the bundle and record
`ree_digest` in metadata. The DOI/PID is a locator and citation handle; the
digest is the content identity.

Later signatures should not require rewriting the sealed REE. They can be:

- included in the initial deposit;
- deposited as a new version;
- stored as sibling attestation artifacts that reference the DOI and
  `ree_digest`;
- indexed by repo2ree while the service exists.

The archive binding claim is therefore:

```text
DOI/PID X resolves to a deposit that contains or references ree_digest Y.
```

## V1 implementation sketch

1. Build the REE and produce Label, runtime artifact, and Run Receipts.
2. Assemble a Seal Manifest from content digests.
3. Canonicalize and compute `ree_digest`.
4. Mark the REE as Sealed; edits require a new seal.
5. Allow optional detached signature envelopes over `ree_digest`.
6. Promote Verify outputs into verification receipts with predecessor links.
7. Allow reviewers or executors to sign verification receipts.
8. Archive the bundle with the Seal Manifest and current signatures.
9. Record DOI/PID and SWHIDs as archive-binding metadata.

The v1 trust story can be modest: unsigned seals still give stable identity.
Signatures can start with author approval and executor attestation, then grow
into reviewer, venue, and institutional claims.

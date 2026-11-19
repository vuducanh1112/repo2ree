"""Verifying the signatures of a sealed REE, or of a review of it: under whose identity each claim counts, and what
a verifier found of each signature.

Sigstore settles what is cryptographic: that the certificate chains to the trust root, that the signature is in the
transparency log and was logged while the certificate held, and that the certificate's key made it. What is the
REE's to say is said here and checked beside it: each statement names the seal it must, under its claim's predicate
type, a review's with the review's record as its predicate; and only the identities a policy names for a claim make
a signature of it ``verified``. A policy is the verifier's own, with no default: a signature no policy names a
signer for is reported with the identity it carries, and never as verified.

Verifying writes nothing: what a verifier found depends on the policy it brought, so it is the verifier's to keep.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.primitives import Digest, UtcInstant

# A claim a signature makes: an author's approval of the seal, or a review of it.
VerifiedClaim = Literal["author_approval", "review"]
# The Sigstore instance whose trust root a verifier holds signatures to; a trust configuration file names another.
TrustRoot = Literal["production", "staging"]
# What a verifier found of one signature, strongest first:
#   verified        Sigstore holds it, its statement is this REE's, and a signer the policy names for its claim made it.
#   signer_unnamed  As verified, but the policy names no signer for its claim: who signed is reported, not judged.
#   other_signer    Sigstore holds it and its statement is this REE's, but a signer the policy does not name made it.
#   not_this_ree    Its statement names another seal, another claim, or a review record other than the one here.
#   untrusted       Sigstore does not hold it: no chain to the trust root, not in the log, or not its key's.
#   unreadable      No Sigstore bundle of an in-toto statement.
VerificationOutcome = Literal["verified", "signer_unnamed", "other_signer", "not_this_ree", "untrusted", "unreadable"]


class _VerificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Signer(_VerificationModel):
    """An identity Sigstore certifies (an email address, or a CI workflow's URI), and the OIDC issuer that proved
    it."""

    identity: str = Field(min_length=1)
    issuer: str = Field(min_length=1)


class VerificationPolicy(_VerificationModel):
    """Whose signature counts for which claim, under which Sigstore's trust root."""

    trust: TrustRoot = "production"
    signers: dict[VerifiedClaim, tuple[Signer, ...]] = Field(default_factory=dict)


class SignatureVerification(_VerificationModel):
    """One signature, as the verifier found it: the signer it carries, when the log recorded it, and why it is not
    verified, where it is not."""

    path: str
    claim: VerifiedClaim | None = None
    outcome: VerificationOutcome
    signer: Signer | None = None
    logged_at: UtcInstant | None = None
    reason: str = ""


class SignatureVerifications(_VerificationModel):
    """Every signature of the REE's seal, or of one review of it, as one verifier found them under its policy."""

    ree_digest: Digest
    review_id: str | None = None
    policy: VerificationPolicy
    signatures: tuple[SignatureVerification, ...] = ()

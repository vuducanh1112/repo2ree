from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.primitives import Digest, UtcInstant

VerifiedClaim = Literal["author_approval", "review"]
TrustRoot = Literal["production", "staging"]
VerificationOutcome = Literal["verified", "signer_unnamed", "other_signer", "not_this_ree", "untrusted", "unreadable"]


class _VerificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Signer(_VerificationModel):
    identity: str = Field(min_length=1)
    issuer: str = Field(min_length=1)


class VerificationPolicy(_VerificationModel):
    trust: TrustRoot = "production"
    signers: dict[VerifiedClaim, tuple[Signer, ...]] = Field(default_factory=dict)


class SignatureVerification(_VerificationModel):
    path: str
    claim: VerifiedClaim | None = None
    outcome: VerificationOutcome
    signer: Signer | None = None
    logged_at: UtcInstant | None = None
    reason: str = ""


class SignatureVerifications(_VerificationModel):
    ree_digest: Digest
    review_id: str | None = None
    policy: VerificationPolicy
    signatures: tuple[SignatureVerification, ...] = ()

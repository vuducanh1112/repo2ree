"""Signed claims about a sealed REE.

Each claim is one Sigstore bundle at ``signatures/<claim>.sigstore.json``, beside what the seal covers: its DSSE
envelope signs an in-toto statement whose subject is the seal's digest, under the claim's predicate type. Reading
the statement says what a bundle claims; whether its signature holds, and whose it is, is a verifier's to say.
"""

from __future__ import annotations

import base64
import binascii
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repo2ree_ree.layout import SIGNATURES

SignatureClaim = Literal["author_approval"]
PREDICATE_TYPES: Final[dict[SignatureClaim, str]] = {
    "author_approval": "https://repo2ree.org/claims/author-approval/v1",
}
SIGNATURE_SUFFIX: Final = ".sigstore.json"
IN_TOTO: Final = "application/vnd.in-toto+json"


def signature_path(claim: SignatureClaim) -> str:
    """Where a claim's signature sits, from the REE root."""
    return f"{SIGNATURES}/{claim}{SIGNATURE_SUFFIX}"


class _Read(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class _Signature(_Read):
    sig: str = Field(min_length=1)


class _Envelope(_Read):
    payload: str
    payload_type: str = Field(alias="payloadType")
    signatures: tuple[_Signature, ...] = Field(min_length=1)


class _Bundle(_Read):
    media_type: str = Field(alias="mediaType", pattern=r"^application/vnd\.dev\.sigstore\.bundle")
    envelope: _Envelope = Field(alias="dsseEnvelope")


class _Subject(_Read):
    digest: dict[str, str]


class _Statement(_Read):
    type: Literal["https://in-toto.io/Statement/v1"] = Field(alias="_type")
    subject: tuple[_Subject, ...] = Field(min_length=1)
    predicate_type: str = Field(alias="predicateType", min_length=1)


class SignedStatement(BaseModel):
    """What a bundle claims: each subject's digest as ``<algorithm>:<hex>``, and the predicate type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    digests: frozenset[str]
    predicate_type: str


class UnreadableSignatureError(ValueError):
    """The content is no Sigstore bundle of a DSSE envelope over an in-toto statement."""


def signed_statement(content: bytes) -> SignedStatement:
    """The statement a Sigstore bundle's DSSE envelope carries; its signature is not checked here."""
    try:
        envelope = _Bundle.model_validate_json(content).envelope
    except ValidationError as exc:
        raise UnreadableSignatureError(f"not a Sigstore bundle of a DSSE envelope: {exc.errors()[0]['msg']}") from exc
    if envelope.payload_type != IN_TOTO:
        raise UnreadableSignatureError(f"the envelope carries {envelope.payload_type}, not an in-toto statement")
    try:
        statement = _Statement.model_validate_json(base64.b64decode(envelope.payload, validate=True))
    except (binascii.Error, ValidationError) as exc:
        raise UnreadableSignatureError("the envelope carries no in-toto statement") from exc
    return SignedStatement(
        digests=frozenset(f"{name}:{value}" for subject in statement.subject for name, value in subject.digest.items()),
        predicate_type=statement.predicate_type,
    )

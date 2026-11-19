"""Signed claims about a sealed REE.

Each claim is one Sigstore bundle at ``signatures/<claim>.sigstore.json``, beside what the seal covers: its DSSE
envelope signs an in-toto statement whose subject is the seal's digest, under the claim's predicate type. A review
of a sealed REE is signed the same way, at its own ``signatures/review.sigstore.json``: the statement names the
reviewed seal, and its predicate is the review's record. A statement is read only once the key its bundle's
certificate holds is found to have made every signature of the envelope. Whether the certificate chains to a trust
root, whose identity it names, and what the transparency log recorded are a verifier's to say.
"""

from __future__ import annotations

import base64
import binascii
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from repo2ree_ree.layout import SIGNATURES

SignatureClaim = Literal["author_approval"]
PREDICATE_TYPES: Final[dict[SignatureClaim, str]] = {
    "author_approval": "https://repo2ree.org/claims/author-approval/v1",
}
# A signed review: its statement's predicate is the review's record, so the one file is the review, signed.
REVIEW_PREDICATE_TYPE: Final = "https://repo2ree.org/claims/review/v1"
SIGNATURE_SUFFIX: Final = ".sigstore.json"
IN_TOTO: Final = "application/vnd.in-toto+json"


def signature_path(claim: SignatureClaim) -> str:
    """Where a claim's signature sits, from the REE root."""
    return f"{SIGNATURES}/{claim}{SIGNATURE_SUFFIX}"


def review_signature_path() -> str:
    """Where a review's signature sits, from the review's root."""
    return f"{SIGNATURES}/review{SIGNATURE_SUFFIX}"


class _Read(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class _RawBytes(_Read):
    raw_bytes: str = Field(alias="rawBytes", min_length=1)


class _Chain(_Read):
    certificates: tuple[_RawBytes, ...] = Field(min_length=1)


class _Material(_Read):
    certificate: _RawBytes | None = None
    chain: _Chain | None = Field(default=None, alias="x509CertificateChain")

    def leaf(self) -> _RawBytes | None:
        return self.certificate or (self.chain.certificates[0] if self.chain else None)


class _Signature(_Read):
    sig: str = Field(min_length=1)


class _Envelope(_Read):
    payload: str
    payload_type: str = Field(alias="payloadType")
    signatures: tuple[_Signature, ...] = Field(min_length=1)


class _Bundle(_Read):
    media_type: str = Field(alias="mediaType", pattern=r"^application/vnd\.dev\.sigstore\.bundle")
    material: _Material = Field(alias="verificationMaterial")
    envelope: _Envelope = Field(alias="dsseEnvelope")


class _Subject(_Read):
    digest: dict[str, str]


class _Statement(_Read):
    type: Literal["https://in-toto.io/Statement/v1"] = Field(alias="_type")
    subject: tuple[_Subject, ...] = Field(min_length=1)
    predicate_type: str = Field(alias="predicateType", min_length=1)
    predicate: JsonValue = None


class SignedStatement(BaseModel):
    """What a bundle claims: each subject's digest as ``<algorithm>:<hex>``, the predicate type, and the
    predicate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    digests: frozenset[str]
    predicate_type: str
    predicate: JsonValue = None


class UnreadableSignatureError(ValueError):
    """The content is no Sigstore bundle of a DSSE envelope over an in-toto statement, with a certificate."""


class UnverifiedSignatureError(ValueError):
    """The envelope has a signature that the key its bundle's certificate holds did not make."""


def _decoded(value: str, what: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise UnreadableSignatureError(f"its {what} is not base64") from exc


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE's pre-authentication encoding: what an envelope's signature is over."""
    kind = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(payload), payload)


def _verify(certificate: bytes, signature: bytes, message: bytes) -> None:
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519

    curve_hashes: dict[str, hashes.HashAlgorithm] = {"secp256r1": hashes.SHA256(), "secp384r1": hashes.SHA384()}
    try:
        key = x509.load_der_x509_certificate(certificate).public_key()
    except ValueError as exc:
        raise UnreadableSignatureError("its certificate is not DER X.509") from exc
    try:
        if isinstance(key, ec.EllipticCurvePublicKey) and key.curve.name in curve_hashes:
            key.verify(signature, message, ec.ECDSA(curve_hashes[key.curve.name]))
        elif isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(signature, message)
        else:
            held = type(key).__name__
            raise UnverifiedSignatureError(f"its certificate holds a key Sigstore does not sign with ({held})")
    except InvalidSignature as exc:
        raise UnverifiedSignatureError("its envelope is not signed by the key its certificate holds") from exc


def signed_statement(content: bytes) -> SignedStatement:
    """The statement a Sigstore bundle's DSSE envelope signs, once every signature of it is found to be the
    certificate key's."""
    try:
        bundle = _Bundle.model_validate_json(content)
    except ValidationError as exc:
        raise UnreadableSignatureError(f"not a Sigstore bundle of a DSSE envelope: {exc.errors()[0]['msg']}") from exc
    leaf = bundle.material.leaf()
    if leaf is None:
        raise UnreadableSignatureError("the bundle holds no certificate: a keyless signature names its signer by one")
    envelope = bundle.envelope
    if envelope.payload_type != IN_TOTO:
        raise UnreadableSignatureError(f"the envelope carries {envelope.payload_type}, not an in-toto statement")
    payload = _decoded(envelope.payload, "payload")
    certificate = _decoded(leaf.raw_bytes, "certificate")
    for signature in envelope.signatures:
        _verify(certificate, _decoded(signature.sig, "signature"), pae(envelope.payload_type, payload))
    try:
        statement = _Statement.model_validate_json(payload)
    except ValidationError as exc:
        raise UnreadableSignatureError("the envelope carries no in-toto statement") from exc
    return SignedStatement(
        digests=frozenset(f"{name}:{value}" for subject in statement.subject for name, value in subject.digest.items()),
        predicate_type=statement.predicate_type,
        predicate=statement.predicate,
    )

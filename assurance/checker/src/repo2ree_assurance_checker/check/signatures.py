"""A Sigstore bundle as the checker reads it: the in-toto statement its DSSE envelope signs, and whether the key
its certificate holds made that signature.

Only what the bundle holds is read. Whether the certificate chains to a trusted root, which identity it names,
and what the transparency log recorded are a verifier's questions, under a trust root and a policy it is given.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Literal

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from pydantic import BaseModel, ConfigDict, Field, ValidationError

IN_TOTO = "application/vnd.in-toto+json"
_CURVE_HASH: dict[str, hashes.HashAlgorithm] = {"secp256r1": hashes.SHA256(), "secp384r1": hashes.SHA384()}


class _Read(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class _RawBytes(_Read):
    raw_bytes: str = Field(alias="rawBytes", min_length=1)


class _Chain(_Read):
    certificates: tuple[_RawBytes, ...] = Field(min_length=1)


class _Material(_Read):
    certificate: _RawBytes | None = None
    chain: _Chain | None = Field(default=None, alias="x509CertificateChain")


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
    name: str = ""
    digest: dict[str, str]


class _Statement(_Read):
    type: Literal["https://in-toto.io/Statement/v1"] = Field(alias="_type")
    subject: tuple[_Subject, ...] = Field(min_length=1)
    predicate_type: str = Field(alias="predicateType", min_length=1)


@dataclass(frozen=True)
class SignedStatement:
    """What a bundle signs: each subject's digest as ``<algorithm>:<hex>``, and the claim's predicate type."""

    digests: frozenset[str]
    predicate_type: str


class UnreadableBundleError(ValueError):
    """The file is no Sigstore bundle of a DSSE in-toto statement, or its signature is not its certificate's."""


def _decoded(value: str, what: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise UnreadableBundleError(f"its {what} is not base64") from exc


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE's pre-authentication encoding: what the signature is over."""
    kind = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(payload), payload)


def _verified(certificate: bytes, signature: bytes, message: bytes) -> None:
    try:
        key = x509.load_der_x509_certificate(certificate).public_key()
    except ValueError as exc:
        raise UnreadableBundleError("its certificate is not DER X.509") from exc
    try:
        if isinstance(key, ec.EllipticCurvePublicKey) and key.curve.name in _CURVE_HASH:
            key.verify(signature, message, ec.ECDSA(_CURVE_HASH[key.curve.name]))
        elif isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(signature, message)
        else:
            held = type(key).__name__
            raise UnreadableBundleError(f"its certificate holds a key Sigstore does not sign with ({held})")
    except InvalidSignature as exc:
        raise UnreadableBundleError("its envelope is not signed by the key its certificate holds") from exc


def signed_statement(content: bytes) -> SignedStatement:
    """The statement a Sigstore bundle signs, once its envelope's every signature is its certificate key's."""
    try:
        bundle = _Bundle.model_validate_json(content)
    except ValidationError as exc:
        raise UnreadableBundleError(f"is not a Sigstore bundle of a DSSE envelope: {exc.errors()[0]['msg']}") from exc
    material = bundle.material
    leaf = material.certificate or (material.chain.certificates[0] if material.chain else None)
    if leaf is None:
        raise UnreadableBundleError("holds no certificate: a keyless signature names its signer by one")
    envelope = bundle.envelope
    if envelope.payload_type != IN_TOTO:
        raise UnreadableBundleError(f"signs a {envelope.payload_type}, not an in-toto statement")
    payload = _decoded(envelope.payload, "payload")
    certificate = _decoded(leaf.raw_bytes, "certificate")
    for signature in envelope.signatures:
        _verified(certificate, _decoded(signature.sig, "signature"), pae(envelope.payload_type, payload))
    try:
        statement = _Statement.model_validate_json(payload)
    except ValidationError as exc:
        raise UnreadableBundleError(f"signs no in-toto statement: {exc.errors()[0]['msg']}") from exc
    return SignedStatement(
        digests=frozenset(
            f"{algorithm}:{value}" for subject in statement.subject for algorithm, value in subject.digest.items()
        ),
        predicate_type=statement.predicate_type,
    )

"""Signatures an exercise asks for, made as a Sigstore signer makes them and handed to ``ree`` as a bundle signed
elsewhere: a DSSE envelope over an in-toto statement, signed by a key a self-signed certificate holds.

Whether a certificate chains to a trust root is a verifier's to say, never the step's; so a bundle made here is one
a signer would have made, or wrong in exactly the way the exercise names.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
from typing import Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from pydantic import JsonValue

from repo2ree_testbed.exercise import ReviewSignature, SealSignature

SEAL_PREDICATE: Final = "https://repo2ree.org/claims/author-approval/v1"
REVIEW_PREDICATE: Final = "https://repo2ree.org/claims/review/v1"
UNKNOWN_PREDICATE: Final = "https://repo2ree.org/claims/unknown/v1"
IN_TOTO: Final = "application/vnd.in-toto+json"
# What a step signs when there is no seal to sign: the step is refused for that, never for the bundle.
NO_SEAL: Final = "sha256:" + "0" * 64
OTHER_SEAL: Final = "sha256:" + hashlib.sha256(b"another seal").hexdigest()


def _certificate(key: ec.EllipticCurvePrivateKey) -> bytes:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sigstore-intermediate")])
    now = datetime.datetime.now(datetime.UTC)
    built = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(minutes=10))
        .sign(key, hashes.SHA256())
    )
    return built.public_bytes(serialization.Encoding.DER)


def _statement(digest: str, predicate_type: str, predicate: JsonValue) -> dict[str, JsonValue]:
    algorithm, _, value = digest.partition(":")
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "ree", "digest": {algorithm: value}}],
        "predicateType": predicate_type,
        "predicate": predicate,
    }


def _pae(payload: bytes) -> bytes:
    kind = IN_TOTO.encode()
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(payload), payload)


def _bundle(
    statement: dict[str, JsonValue], *, foreign_key: bool = False, carried: dict[str, JsonValue] | None = None
) -> bytes:
    signer = ec.generate_private_key(ec.SECP256R1())
    holder = ec.generate_private_key(ec.SECP256R1()) if foreign_key else signer
    signed = json.dumps(statement).encode()
    signature = signer.sign(_pae(signed), ec.ECDSA(hashes.SHA256()))
    payload = signed if carried is None else json.dumps(carried).encode()
    return json.dumps(
        {
            "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
            "verificationMaterial": {"certificate": {"rawBytes": base64.b64encode(_certificate(holder)).decode()}},
            "dsseEnvelope": {
                "payload": base64.b64encode(payload).decode(),
                "payloadType": IN_TOTO,
                "signatures": [{"sig": base64.b64encode(signature).decode(), "keyid": ""}],
            },
        }
    ).encode()


def seal_bundle(seal: str | None, signature: SealSignature) -> bytes:
    """A bundle over the seal ``seal`` under the author's approval, or wrong in the one way ``signature`` names."""
    digest = seal or NO_SEAL
    statement = _statement(digest, SEAL_PREDICATE, {})
    match signature:
        case "valid":
            return _bundle(statement)
        case "foreign_key":
            return _bundle(statement, foreign_key=True)
        case "other_seal":
            return _bundle(_statement(OTHER_SEAL, SEAL_PREDICATE, {}))
        case "other_claim":
            return _bundle(_statement(digest, UNKNOWN_PREDICATE, {}))
        case "tampered":
            return _bundle(statement, carried=_statement(OTHER_SEAL, SEAL_PREDICATE, {}))


def review_bundle(seal: str | None, record: JsonValue, signature: ReviewSignature) -> bytes:
    """A bundle over the reviewed seal with the review's record as its predicate, or wrong in the one way
    ``signature`` names."""
    digest = seal or NO_SEAL
    statement = _statement(digest, REVIEW_PREDICATE, record)
    match signature:
        case "valid":
            return _bundle(statement)
        case "foreign_key":
            return _bundle(statement, foreign_key=True)
        case "other_seal":
            return _bundle(_statement(OTHER_SEAL, REVIEW_PREDICATE, record))
        case "other_record":
            return _bundle(_statement(digest, REVIEW_PREDICATE, {"record": "another"}))
        case "tampered":
            return _bundle(statement, carried=_statement(digest, REVIEW_PREDICATE, {"record": "another"}))

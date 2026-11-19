"""Sigstore bundles as a signer makes them, without Sigstore: a DSSE envelope over an in-toto statement, signed by a
key that a self-signed certificate holds."""

from __future__ import annotations

import base64
import datetime
import json
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from repo2ree_ree.signature import IN_TOTO, pae


def certificate(key: ec.EllipticCurvePrivateKey) -> bytes:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sigstore-intermediate")])
    now = datetime.datetime(2026, 11, 19, tzinfo=datetime.UTC)
    built = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(minutes=10))
        .sign(key, hashes.SHA256())
    )
    return built.public_bytes(serialization.Encoding.DER)


def statement_of(digest: str, predicate_type: str, predicate: Any = None) -> dict[str, Any]:
    algorithm, _, value = digest.partition(":")
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "ree", "digest": {algorithm: value}}],
        "predicateType": predicate_type,
        "predicate": {} if predicate is None else predicate,
    }


def signed_bundle(
    statement: dict[str, Any],
    *,
    signer: ec.EllipticCurvePrivateKey | None = None,
    holder: ec.EllipticCurvePrivateKey | None = None,
    carried: dict[str, Any] | None = None,
) -> bytes:
    """``statement`` signed by ``signer``, in a bundle whose certificate holds ``holder``'s key (the signer's unless
    a test says otherwise) and whose envelope carries ``carried`` (the statement signed unless a test says
    otherwise)."""
    signer = signer or ec.generate_private_key(ec.SECP256R1())
    signed = json.dumps(statement).encode()
    signature = signer.sign(pae(IN_TOTO, signed), ec.ECDSA(hashes.SHA256()))
    payload = signed if carried is None else json.dumps(carried).encode()
    held = base64.b64encode(certificate(holder or signer)).decode()
    return json.dumps(
        {
            "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
            "verificationMaterial": {"certificate": {"rawBytes": held}},
            "dsseEnvelope": {
                "payload": base64.b64encode(payload).decode(),
                "payloadType": IN_TOTO,
                "signatures": [{"sig": base64.b64encode(signature).decode(), "keyid": ""}],
            },
        }
    ).encode()

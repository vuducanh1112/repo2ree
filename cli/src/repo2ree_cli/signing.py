"""Sign a sealed REE, or a review of one, with Sigstore: an in-toto statement over the seal's digest, as a DSSE
envelope in a bundle. A review's statement carries the review's record as its predicate.

The signer proves who they are to an OIDC issuer: in a browser, by a code pasted from one, or by a token the
environment already holds, as a CI job does. Fulcio certifies a key for that identity for a few minutes, and Rekor
logs the signature publicly. The bundle carries all three, and core keeps it beside the seal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from repo2ree_ree.digest import DIGEST_PREFIX
from repo2ree_ree.instant import parse_utc_instant
from repo2ree_ree.primitives import Digest, UtcInstant
from repo2ree_ree.signature import PREDICATE_TYPES, REVIEW_PREDICATE_TYPE, UnreadableSignatureError, signed_statement
from repo2ree_ree.verification import (
    SignatureVerification,
    Signer,
    TrustRoot,
    VerificationOutcome,
    VerificationPolicy,
    VerifiedClaim,
)

SigstoreInstance = Literal["production", "staging"]

PUBLIC_LOG_NOTICE = (
    "Signing records your identity (an email address, or a CI workflow) in Sigstore's public transparency log, "
    "for good."
)


class SigningRequest(BaseModel):
    """What to sign, and where the signer's identity and Sigstore's services come from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ree_name: str
    ree_digest: Digest
    predicate_type: str
    predicate: dict[str, JsonValue] = Field(default_factory=dict)
    instance: SigstoreInstance = "production"
    # A Sigstore client trust configuration naming other services, such as a local stack; it wins over instance.
    trust_config: Path | None = None
    identity_token: str | None = None
    # Paste a code from the browser instead of letting the issuer redirect to this machine.
    out_of_band: bool = False


# Why nothing was signed: this ree has no Sigstore client, a service was out of reach, or Sigstore refused.
SigningFailure = Literal["precondition", "unavailable", "execution"]


class SigningError(Exception):
    def __init__(self, message: str, *, category: SigningFailure) -> None:
        super().__init__(message)
        self.category: SigningFailure = category


def sign_seal(request: SigningRequest) -> bytes:
    """The Sigstore bundle of the request's statement, signed under the identity the signer proves."""
    try:
        from sigstore.errors import Error, NetworkError
        from sigstore.oidc import ExpiredIdentity, IssuerError
    except ModuleNotFoundError as exc:
        raise SigningError(
            "this ree has no Sigstore client: sign with one that has, or add a bundle signed elsewhere with --bundle",
            category="precondition",
        ) from exc
    try:
        return _signed(request)
    except NetworkError as exc:
        raise SigningError(f"Sigstore is out of reach: {exc}", category="unavailable") from exc
    except (Error, IssuerError, ExpiredIdentity) as exc:
        raise SigningError(f"Sigstore did not sign: {exc}", category="execution") from exc


def _signed(request: SigningRequest) -> bytes:
    from sigstore.dsse import DigestSet, StatementBuilder, Subject
    from sigstore.models import ClientTrustConfig
    from sigstore.oidc import IdentityToken, Issuer, detect_credential
    from sigstore.sign import SigningContext

    if request.trust_config is not None:
        trust = ClientTrustConfig.from_json(request.trust_config.read_text(encoding="utf-8"))
    elif request.instance == "staging":
        trust = ClientTrustConfig.staging()
    else:
        trust = ClientTrustConfig.production()
    raw = request.identity_token or detect_credential()
    identity = (
        IdentityToken(raw)
        if raw
        else Issuer(trust.signing_config.get_oidc_url()).identity_token(force_oob=request.out_of_band)
    )
    sha256 = str(request.ree_digest).removeprefix(DIGEST_PREFIX)
    signed = (
        StatementBuilder()
        .subjects([Subject(name=request.ree_name, digest=DigestSet({"sha256": sha256}))])
        .predicate_type(request.predicate_type)
        .predicate(request.predicate)
        .build()
    )
    # One key for the certificate and the signature: without its cache, sigstore makes a new key each time it
    # is asked for one, and the signature is not the certificate's.
    with SigningContext.from_trust_config(trust).signer(identity) as signer:
        return signer.sign_dsse(signed).to_json().encode()


# ================================================
# Verifying
# ================================================


class _Held(BaseModel):
    """What Sigstore holds of a bundle it accepted: the signer its certificate names, and when the log recorded it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signer: Signer
    logged_at: UtcInstant | None = None


class _UntrustedError(Exception):
    """Sigstore did not accept the bundle."""


def _trusted_root(trust: TrustRoot, trust_config: Path | None) -> Any:
    from sigstore.models import ClientTrustConfig

    if trust_config is not None:
        return ClientTrustConfig.from_json(trust_config.read_text(encoding="utf-8")).trusted_root
    return (ClientTrustConfig.staging() if trust == "staging" else ClientTrustConfig.production()).trusted_root


def _signer_of(certificate: Any) -> Signer:
    """The identity a Fulcio certificate certifies, and the OIDC issuer that proved it."""
    from cryptography import x509

    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    identities = [
        *names.get_values_for_type(x509.RFC822Name),
        *names.get_values_for_type(x509.UniformResourceIdentifier),
    ]
    issuer = ""
    for oid, encoded in ((_ISSUER_V2, True), (_ISSUER, False)):
        try:
            raw = certificate.extensions.get_extension_for_oid(x509.ObjectIdentifier(oid)).value.value
        except x509.ExtensionNotFound:
            continue
        # The second issuer extension is a DER UTF8String: a tag, a length, then the value.
        issuer = raw[2:].decode() if encoded else raw.decode()
        break
    return Signer(identity=identities[0] if identities else "(none)", issuer=issuer or "(none)")


_ISSUER = "1.3.6.1.4.1.57264.1.1"
_ISSUER_V2 = "1.3.6.1.4.1.57264.1.8"


def sigstore_holds(content: bytes, trust: TrustRoot, trust_config: Path | None) -> _Held:
    """What Sigstore holds of a bundle under the trust root: the chain, the log, and the key that signed. Whose
    identity it names is not judged here."""
    import json

    from sigstore.errors import Error
    from sigstore.models import Bundle
    from sigstore.verify import Verifier, policy

    try:
        bundle = Bundle.from_json(content)
        Verifier(trusted_root=_trusted_root(trust, trust_config)).verify_dsse(bundle, policy.UnsafeNoOp())
    except (Error, ValueError) as exc:
        raise _UntrustedError(str(exc)) from exc
    entries = json.loads(content).get("verificationMaterial", {}).get("tlogEntries", [])
    logged = entries[0].get("integratedTime") if entries else None
    logged_at = (
        parse_utc_instant(datetime.fromtimestamp(int(logged), tz=UTC)) if isinstance(logged, str | int) else None
    )
    return _Held(signer=_signer_of(bundle.signing_certificate), logged_at=logged_at)


def verify_signature(
    content: bytes,
    *,
    path: str,
    claim: VerifiedClaim | None,
    seal: Digest,
    record: JsonValue | None,
    policy: VerificationPolicy,
    trust_config: Path | None = None,
) -> SignatureVerification:
    """One signature, as a verifier finds it under ``policy``: the REE's own checks first, then Sigstore's, then whose.

    ``record`` is the review's record a review's signature must carry; None for a signature of the seal.
    """
    try:
        statement = signed_statement(content)
    except UnreadableSignatureError as exc:
        return SignatureVerification(path=path, claim=claim, outcome="unreadable", reason=str(exc))
    if claim is None:
        return SignatureVerification(path=path, outcome="not_this_ree", reason="is named for no claim")
    expected = REVIEW_PREDICATE_TYPE if claim == "review" else PREDICATE_TYPES[claim]
    if str(seal) not in statement.digests:
        reason = f"signs {', '.join(sorted(statement.digests))}, not the seal {seal}"
        return SignatureVerification(path=path, claim=claim, outcome="not_this_ree", reason=reason)
    if statement.predicate_type != expected:
        reason = f"claims {statement.predicate_type}, not {expected}"
        return SignatureVerification(path=path, claim=claim, outcome="not_this_ree", reason=reason)
    if claim == "review" and statement.predicate != record:
        reason = "signs another record than the review holds"
        return SignatureVerification(path=path, claim=claim, outcome="not_this_ree", reason=reason)
    try:
        held = sigstore_holds(content, policy.trust, trust_config)
    except _UntrustedError as exc:
        return SignatureVerification(path=path, claim=claim, outcome="untrusted", reason=str(exc))
    named = policy.signers.get(claim, ())
    if not named:
        outcome: VerificationOutcome = "signer_unnamed"
        reason = f"the policy names no signer for {claim}"
    elif held.signer in named:
        outcome, reason = "verified", ""
    else:
        outcome = "other_signer"
        reason = f"signed by {held.signer.identity} ({held.signer.issuer}), whom the policy does not name for {claim}"
    return SignatureVerification(
        path=path, claim=claim, outcome=outcome, signer=held.signer, logged_at=held.logged_at, reason=reason
    )

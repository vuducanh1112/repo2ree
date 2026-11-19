"""Sign a sealed REE with Sigstore: an in-toto statement over the seal's digest, as a DSSE envelope in a bundle.

The signer proves who they are to an OIDC issuer: in a browser, by a code pasted from one, or by a token the
environment already holds, as a CI job does. Fulcio certifies a key for that identity for a few minutes, and Rekor
logs the signature publicly. The bundle carries all three, and core keeps it beside the seal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_ree.digest import DIGEST_PREFIX
from repo2ree_ree.primitives import Digest
from repo2ree_ree.signature import PREDICATE_TYPES, SignatureClaim

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
    claim: SignatureClaim
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
        .predicate_type(PREDICATE_TYPES[request.claim])
        .predicate({})
        .build()
    )
    # One key for the certificate and the signature: without its cache, sigstore makes a new key each time it
    # is asked for one, and the signature is not the certificate's.
    with SigningContext.from_trust_config(trust).signer(identity) as signer:
        return signer.sign_dsse(signed).to_json().encode()

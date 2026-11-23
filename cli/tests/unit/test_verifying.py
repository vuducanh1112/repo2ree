from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from cryptography.hazmat.primitives.asymmetric import ed25519
from test_signing import TOKEN, answered, bundle, draft, ree, requests, reviewed, seal_of, sealed

from repo2ree_cli import signing
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.primitives import Digest
from repo2ree_ree.signature import PREDICATE_TYPES, REVIEW_PREDICATE_TYPE, review_signature_path, signature_path
from repo2ree_ree.verification import SignatureVerifications, Signer

__all__ = ["draft", "requests", "sealed"]

AUTHOR = Signer(identity="author@example.org", issuer="https://issuer.example.org")
OTHER = Signer(identity="someone@example.org", issuer="https://issuer.example.org")


@pytest.fixture
def sigstore(monkeypatch: pytest.MonkeyPatch) -> dict[str, Signer | str]:
    held: dict[str, Signer | str] = {"signer": AUTHOR}

    def holds(content: bytes, trust: str, trust_config: Path | None) -> object:
        if "untrusted" in held:
            raise signing._UntrustedError(str(held["untrusted"]))
        signer = held["signer"]
        assert isinstance(signer, Signer)
        return signing._Held(signer=signer)

    monkeypatch.setattr(signing, "sigstore_holds", holds)
    return held


def signed_by_author(root: Path) -> Path:
    request = signing.SigningRequest(
        ree_name="demo", ree_digest=Digest(seal_of(root)), predicate_type=PREDICATE_TYPES["author_approval"]
    )
    path = root / signature_path("author_approval")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bundle(request))
    return path


def verified(result: Result) -> SignatureVerifications:
    return SignatureVerifications.model_validate(answered(result).outputs)


def policy_of(signer: Signer) -> tuple[str, ...]:
    return ("--identity", signer.identity, "--issuer", signer.issuer)


def test_the_author_s_signature_is_verified_under_a_policy_that_names_its_signer(
    sealed: Path, sigstore: dict[str, Signer | str]
) -> None:
    signed_by_author(sealed)

    result = ree(sealed, "verify-signatures", *policy_of(AUTHOR))

    assert answered(result).status == "succeeded", result.output
    [found] = verified(result).signatures
    assert (found.path, found.claim, found.outcome, found.signer) == (
        "signatures/author_approval.sigstore.json",
        "author_approval",
        "verified",
        AUTHOR,
    )


@pytest.mark.parametrize(
    ("signer", "policy", "outcome"),
    [(OTHER, policy_of(AUTHOR), "other_signer"), (AUTHOR, (), "signer_unnamed")],
)
def test_a_signature_whose_signer_the_policy_does_not_name_is_reported_and_never_verified(
    sealed: Path, sigstore: dict[str, Signer | str], signer: Signer, policy: tuple[str, ...], outcome: str
) -> None:
    signed_by_author(sealed)
    sigstore["signer"] = signer

    result = ree(sealed, "verify-signatures", *policy)

    assert answered(result).status == "failed"
    [found] = verified(result).signatures
    assert (found.outcome, found.signer) == (outcome, signer)


def test_a_signature_sigstore_does_not_hold_is_untrusted(sealed: Path, sigstore: dict[str, Signer | str]) -> None:
    signed_by_author(sealed)
    sigstore["untrusted"] = "the certificate chains to no root here"

    result = ree(sealed, "verify-signatures", *policy_of(AUTHOR))

    [found] = verified(result).signatures
    assert (found.outcome, found.signer, found.reason) == ("untrusted", None, "the certificate chains to no root here")


def test_a_signature_its_certificate_s_key_did_not_make_is_untrusted_before_sigstore_is_asked(
    sealed: Path, sigstore: dict[str, Signer | str]
) -> None:
    request = signing.SigningRequest(
        ree_name="demo", ree_digest=Digest(seal_of(sealed)), predicate_type=PREDICATE_TYPES["author_approval"]
    )
    path = sealed / signature_path("author_approval")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bundle(request, holder=ed25519.Ed25519PrivateKey.generate()))

    result = ree(sealed, "verify-signatures", *policy_of(AUTHOR))

    assert answered(result).status == "failed"
    [found] = verified(result).signatures
    assert (found.outcome, found.signer) == ("untrusted", None)
    assert found.reason == "its envelope is not signed by the key its certificate holds"


def test_a_signature_of_another_seal_is_not_this_ree_s_whoever_signed_it(
    sealed: Path, sigstore: dict[str, Signer | str]
) -> None:
    request = signing.SigningRequest(
        ree_name="demo", ree_digest=Digest("sha256:" + "0" * 64), predicate_type=PREDICATE_TYPES["author_approval"]
    )
    path = sealed / signature_path("author_approval")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bundle(request))

    [found] = verified(ree(sealed, "verify-signatures", *policy_of(AUTHOR))).signatures

    assert found.outcome == "not_this_ree"
    assert found.signer is None, "Sigstore is never asked about a statement that is not this REE's"


def test_nothing_signed_fails(sealed: Path, sigstore: dict[str, Signer | str]) -> None:
    result = ree(sealed, "verify-signatures", *policy_of(AUTHOR))

    failure = answered(result).failure
    assert failure is not None
    assert failure.message == "nothing here is signed"


def test_a_review_s_signature_is_verified_with_the_record_it_holds(
    sealed: Path, sigstore: dict[str, Signer | str], requests: list[signing.SigningRequest]
) -> None:
    reviewed(sealed, "r1", seal_of(sealed))
    assert answered(ree(sealed, "sign-review", "--review-id", "r1", "--identity-token", TOKEN)).status == "succeeded"

    result = ree(sealed, "verify-signatures", "--review-id", "r1", *policy_of(AUTHOR))

    assert answered(result).status == "succeeded", result.output
    [found] = verified(result).signatures
    assert (found.path, found.claim, found.outcome) == (review_signature_path(), "review", "verified")


def test_a_review_whose_record_is_not_the_one_signed_is_not_this_ree_s(
    sealed: Path, sigstore: dict[str, Signer | str], requests: list[signing.SigningRequest]
) -> None:
    record = reviewed(sealed, "r1", seal_of(sealed))
    assert answered(ree(sealed, "sign-review", "--review-id", "r1", "--identity-token", TOKEN)).status == "succeeded"
    edited = json.loads(record.read_bytes()) | {"status": "failed"}
    record.write_text(json.dumps(edited))

    [found] = verified(ree(sealed, "verify-signatures", "--review-id", "r1", *policy_of(AUTHOR))).signatures

    assert found.outcome == "not_this_ree"
    assert found.reason == "signs another record than the review holds"
    assert REVIEW_PREDICATE_TYPE in requests[0].predicate_type


def test_a_policy_is_a_file_or_one_signer_not_both(sealed: Path, tmp_path: Path) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"signers": {"author_approval": [AUTHOR.model_dump()]}}))

    both = answered(ree(sealed, "verify-signatures", "--policy", str(policy), *policy_of(AUTHOR)))
    half = answered(ree(sealed, "verify-signatures", "--identity", AUTHOR.identity))

    assert both.failure is not None
    assert both.failure.category == "validation"
    assert half.failure is not None
    assert half.failure.category == "validation"
    assert not (ReeLayout(root=sealed).root / "signatures").exists()

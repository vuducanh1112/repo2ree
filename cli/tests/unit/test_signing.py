"""`ree sign-ree` signs the sealed REE with Sigstore and keeps the bundle beside the seal, and `ree sign-review`
signs a review of it with the review's record as the statement's predicate; the network is faked."""

from __future__ import annotations

import base64
import datetime
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID

from repo2ree_cli import signing
from repo2ree_cli.cli import REFUSED, cli
from repo2ree_core.evidence.review.records import new_review_record, with_step
from repo2ree_core.evidence.review.store import write_review_record
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.instant import parse_utc_instant
from repo2ree_ree.primitives import Digest
from repo2ree_ree.review import ReviewSubject
from repo2ree_ree.signature import (
    IN_TOTO,
    PREDICATE_TYPES,
    REVIEW_PREDICATE_TYPE,
    pae,
    review_signature_path,
    signature_path,
)

runner = CliRunner()
SIGNATURE = signature_path("author_approval")
TOKEN = "an-oidc-token-that-never-reaches-the-ree"  # noqa: S105 — a stand-in, never a credential


def ree(root: Path, *words: str, env: dict[str, str] | None = None) -> Result:
    return runner.invoke(cli, ["-C", str(root), "--json", *words], env=env)


def answered(result: Result) -> ActionResult:
    return ActionResult.model_validate_json(result.stdout)


# Ed25519 signs deterministically, so the bundle a request makes is the same bytes every time.
SIGNER = ed25519.Ed25519PrivateKey.from_private_bytes(bytes(32))


def certificate(key: ed25519.Ed25519PrivateKey) -> bytes:
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
        .sign(key, None)
    )
    return built.public_bytes(serialization.Encoding.DER)


def bundle(request: signing.SigningRequest, *, holder: ed25519.Ed25519PrivateKey = SIGNER) -> bytes:
    """What Sigstore makes of ``request``: signed by SIGNER, in a bundle whose certificate holds ``holder``'s key."""
    algorithm, _, value = str(request.ree_digest).partition(":")
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": request.ree_name, "digest": {algorithm: value}}],
        "predicateType": request.predicate_type,
        "predicate": request.predicate,
    }
    payload = json.dumps(statement).encode()
    return json.dumps(
        {
            "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
            "verificationMaterial": {"certificate": {"rawBytes": base64.b64encode(certificate(holder)).decode()}},
            "dsseEnvelope": {
                "payload": base64.b64encode(payload).decode(),
                "payloadType": IN_TOTO,
                "signatures": [{"sig": base64.b64encode(SIGNER.sign(pae(IN_TOTO, payload))).decode(), "keyid": ""}],
            },
        }
    ).encode()


@pytest.fixture
def requests(monkeypatch: pytest.MonkeyPatch) -> list[signing.SigningRequest]:
    asked: list[signing.SigningRequest] = []

    def sign_seal(request: signing.SigningRequest) -> bytes:
        asked.append(request)
        return bundle(request)

    monkeypatch.setattr(signing, "sign_seal", sign_seal)
    return asked


@pytest.fixture
def draft(tmp_path: Path) -> Path:
    root = tmp_path / "ree"
    assert runner.invoke(cli, ["-C", str(root), "initialize-ree", "--name", "demo"]).exit_code == 0
    return root


@pytest.fixture
def sealed(draft: Path) -> Path:
    result = ree(draft, "seal-ree", "--no-source-included", "--no-results-included")
    assert answered(result).status == "succeeded", result.output
    return draft


def seal_of(root: Path) -> str:
    seal = ReeDirectory(ReeLayout(root=root)).read_ree().seal
    assert seal is not None
    return str(seal.ree_digest)


def test_signing_signs_the_seal_s_digest_and_keeps_the_bundle_beside_it(
    sealed: Path, requests: list[signing.SigningRequest]
) -> None:
    result = ree(sealed, "sign-ree", "--staging", "--identity-token", TOKEN)

    assert answered(result).status == "succeeded", result.output
    [request] = requests
    assert request.ree_name == "demo"
    assert str(request.ree_digest) == seal_of(sealed)
    assert request.predicate_type == PREDICATE_TYPES["author_approval"]
    assert request.instance == "staging"
    assert request.identity_token == TOKEN
    assert (sealed / SIGNATURE).read_bytes() == bundle(request)
    assert signing.PUBLIC_LOG_NOTICE in result.stderr


def test_the_identity_token_comes_from_the_environment_and_never_reaches_the_ree(
    sealed: Path, requests: list[signing.SigningRequest]
) -> None:
    result = ree(sealed, "sign-ree", env={"SIGSTORE_IDENTITY_TOKEN": TOKEN})

    assert answered(result).status == "succeeded", result.output
    assert requests[0].identity_token == TOKEN
    assert requests[0].instance == "production"
    with open_history(ReeLayout(root=sealed)) as history:
        recorded = history.git("log", "--all", "--format=%B").stdout
        trees = history.git("grep", "-I", "-c", TOKEN, "HEAD", check=False).stdout
    assert TOKEN.encode() not in recorded
    assert not trees


def test_a_draft_is_refused_before_anyone_signs_in(draft: Path, requests: list[signing.SigningRequest]) -> None:
    result = ree(draft, "sign-ree")

    assert result.exit_code == REFUSED
    failure = answered(result).failure
    assert failure is not None
    assert failure.category == "precondition"
    assert requests == []
    assert signing.PUBLIC_LOG_NOTICE not in result.stderr


@pytest.mark.parametrize("category", ["precondition", "unavailable", "execution"])
def test_sigstore_that_does_not_sign_leaves_the_ree_unsigned(
    sealed: Path, monkeypatch: pytest.MonkeyPatch, category: signing.SigningFailure
) -> None:
    def sign_seal(_request: signing.SigningRequest) -> Any:
        raise signing.SigningError("no", category=category)

    monkeypatch.setattr(signing, "sign_seal", sign_seal)
    result = ree(sealed, "sign-ree")

    failure = answered(result).failure
    assert failure is not None
    assert failure.category == category
    assert not (sealed / SIGNATURE).exists()


def test_a_bundle_signed_elsewhere_is_added_without_signing_here(
    sealed: Path, tmp_path: Path, requests: list[signing.SigningRequest]
) -> None:
    elsewhere = tmp_path / "approval.sigstore.json"
    request = signing.SigningRequest(
        ree_name="demo", ree_digest=Digest(seal_of(sealed)), predicate_type=PREDICATE_TYPES["author_approval"]
    )
    elsewhere.write_bytes(bundle(request))

    result = ree(sealed, "sign-ree", "--bundle", str(elsewhere))

    assert answered(result).status == "succeeded", result.output
    assert requests == []
    assert (sealed / SIGNATURE).read_bytes() == elsewhere.read_bytes()


def test_a_ree_without_a_sigstore_client_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sigstore.errors", None)
    request = signing.SigningRequest(
        ree_name="demo", ree_digest=Digest("sha256:" + "0" * 64), predicate_type=PREDICATE_TYPES["author_approval"]
    )
    with pytest.raises(signing.SigningError, match="no Sigstore client") as raised:
        signing.sign_seal(request)
    assert raised.value.category == "precondition"


def reviewed(root: Path, review_id: str, seal: str | None) -> Path:
    """A settled review of the REE at ``root``, of its seal or of a draft: where its record is."""
    review = ReeLayout(root=root).review(review_id)
    at = parse_utc_instant("2026-11-19T00:00:00Z")
    record = with_step(
        new_review_record(
            review_id, subject=ReviewSubject(name="demo", ree_digest=Digest(seal) if seal else None), at=at
        ),
        "acquire_source",
        status="completed",
        at=at,
    )
    review.root.mkdir(parents=True)
    write_review_record(review, record)
    return review.metadata


def test_a_review_is_signed_with_its_record_as_the_predicate(
    sealed: Path, requests: list[signing.SigningRequest]
) -> None:
    record = reviewed(sealed, "r1", seal_of(sealed))

    result = ree(sealed, "sign-review", "--review-id", "r1", "--staging", "--identity-token", TOKEN)

    assert answered(result).status == "succeeded", result.output
    [request] = requests
    assert str(request.ree_digest) == seal_of(sealed)
    assert request.predicate_type == REVIEW_PREDICATE_TYPE
    assert request.predicate == json.loads(record.read_bytes())
    signature = ReeLayout(root=sealed).review("r1").root / review_signature_path()
    assert signature.read_bytes() == bundle(request)
    assert not (sealed / SIGNATURE).exists(), "a review's signature is the review's, not the REE's"
    with open_history(ReeLayout(root=sealed).review("r1")) as history:
        committed = history.git("ls-tree", "-r", "--name-only", "HEAD").stdout.decode().split()
    assert review_signature_path() in committed, "the review's history holds its signature, as a download carries it"


def test_a_review_of_a_draft_is_refused_before_anyone_signs_in(
    draft: Path, requests: list[signing.SigningRequest]
) -> None:
    reviewed(draft, "r1", None)

    result = ree(draft, "sign-review", "--review-id", "r1")

    failure = answered(result).failure
    assert failure is not None
    assert failure.category == "precondition"
    assert requests == []


def test_a_bundle_over_another_record_is_refused(sealed: Path, tmp_path: Path) -> None:
    reviewed(sealed, "r1", seal_of(sealed))
    elsewhere = tmp_path / "review.sigstore.json"
    other = signing.SigningRequest(
        ree_name="demo",
        ree_digest=Digest(seal_of(sealed)),
        predicate_type=REVIEW_PREDICATE_TYPE,
        predicate={"review_id": "another"},
    )
    elsewhere.write_bytes(bundle(other))

    result = ree(sealed, "sign-review", "--review-id", "r1", "--bundle", str(elsewhere))

    failure = answered(result).failure
    assert failure is not None
    assert failure.category == "validation"
    assert "another record" in failure.message
    assert not (ReeLayout(root=sealed).review("r1").root / review_signature_path()).exists()


def test_a_signed_review_changes_no_more(sealed: Path, requests: list[signing.SigningRequest]) -> None:
    reviewed(sealed, "r1", seal_of(sealed))
    assert answered(ree(sealed, "sign-review", "--review-id", "r1", "--identity-token", TOKEN)).status == "succeeded"

    again = answered(ree(sealed, "review", "acquire-source", "--review-id", "r1"))
    built = answered(ree(sealed, "review", "build-experiment-environment", "--review-id", "r1"))
    resigned = answered(ree(sealed, "sign-review", "--review-id", "r1", "--identity-token", TOKEN))

    for refused in (again, built):
        assert refused.failure is not None
        assert "changes no more" in refused.failure.message
    assert resigned.failure is not None
    assert "signed already" in resigned.failure.message


def test_a_review_bundle_its_certificate_s_key_did_not_make_is_refused_and_leaves_the_review_open(
    sealed: Path, tmp_path: Path
) -> None:
    record = reviewed(sealed, "r1", seal_of(sealed))
    elsewhere = tmp_path / "review.sigstore.json"
    request = signing.SigningRequest(
        ree_name="demo",
        ree_digest=Digest(seal_of(sealed)),
        predicate_type=REVIEW_PREDICATE_TYPE,
        predicate=json.loads(record.read_bytes()),
    )
    elsewhere.write_bytes(bundle(request, holder=ed25519.Ed25519PrivateKey.generate()))

    result = ree(sealed, "sign-review", "--review-id", "r1", "--bundle", str(elsewhere))

    failure = answered(result).failure
    assert failure is not None
    assert failure.category == "validation"
    assert "not signed by the key its certificate holds" in failure.message
    assert not (ReeLayout(root=sealed).review("r1").root / review_signature_path()).exists()
    elsewhere.write_bytes(bundle(request))
    signed = ree(sealed, "sign-review", "--review-id", "r1", "--bundle", str(elsewhere))
    assert answered(signed).status == "succeeded", signed.output

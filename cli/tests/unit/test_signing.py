"""`ree sign-ree` signs the sealed REE with Sigstore and keeps the bundle beside the seal; the network is faked."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result

from repo2ree_cli import signing
from repo2ree_cli.cli import REFUSED, cli
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.primitives import Digest
from repo2ree_ree.signature import PREDICATE_TYPES, signature_path

runner = CliRunner()
SIGNATURE = signature_path("author_approval")
TOKEN = "an-oidc-token-that-never-reaches-the-ree"  # noqa: S105 — a stand-in, never a credential


def ree(root: Path, *words: str, env: dict[str, str] | None = None) -> Result:
    return runner.invoke(cli, ["-C", str(root), "--json", *words], env=env)


def answered(result: Result) -> ActionResult:
    return ActionResult.model_validate_json(result.stdout)


def bundle(request: signing.SigningRequest) -> bytes:
    algorithm, _, value = str(request.ree_digest).partition(":")
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": request.ree_name, "digest": {algorithm: value}}],
        "predicateType": PREDICATE_TYPES[request.claim],
        "predicate": {},
    }
    return json.dumps(
        {
            "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
            "verificationMaterial": {"certificate": {"rawBytes": "MA=="}},
            "dsseEnvelope": {
                "payload": base64.b64encode(json.dumps(statement).encode()).decode(),
                "payloadType": "application/vnd.in-toto+json",
                "signatures": [{"sig": "MA==", "keyid": ""}],
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
    assert request.claim == "author_approval"
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
    request = signing.SigningRequest(ree_name="demo", ree_digest=Digest(seal_of(sealed)), claim="author_approval")
    elsewhere.write_bytes(bundle(request))

    result = ree(sealed, "sign-ree", "--bundle", str(elsewhere))

    assert answered(result).status == "succeeded", result.output
    assert requests == []
    assert (sealed / SIGNATURE).read_bytes() == elsewhere.read_bytes()


def test_a_ree_without_a_sigstore_client_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sigstore.errors", None)
    request = signing.SigningRequest(ree_name="demo", ree_digest=Digest("sha256:" + "0" * 64), claim="author_approval")
    with pytest.raises(signing.SigningError, match="no Sigstore client") as raised:
        signing.sign_seal(request)
    assert raised.value.category == "precondition"

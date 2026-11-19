"""The run's own Sigstore, as far as it is checked without starting it: its trust configuration and its tokens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sigstore.models import ClientTrustConfig
from sigstore.oidc import IdentityToken

from repo2ree_testbed.stack.sigstore import (
    IDENTITY,
    SIGSTORE_VARIABLE,
    LocalSigstore,
    SigstoreStack,
    _root_ca,
    local_sigstore,
)


def written(tmp_path: Path) -> LocalSigstore:
    key = ec.generate_private_key(ec.SECP256R1())
    (tmp_path / "issuer.key").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return LocalSigstore(
        trust_config=tmp_path / "trust_config.json",
        issuer="http://issuer.invalid:8080",
        identity=IDENTITY,
        signing_key=tmp_path / "issuer.key",
    )


def test_the_trust_configuration_is_one_sigstore_reads(tmp_path: Path) -> None:
    stack = SigstoreStack(tmp_path, tmp_path / "log")
    _, root = _root_ca()
    keys = [ec.generate_private_key(ec.SECP256R1()).public_key() for _ in range(2)]
    config = stack._trust_config("http://issuer.invalid:8080", root, keys[0], keys[1])

    trust = ClientTrustConfig.from_json(json.dumps(config))

    assert trust.signing_config.get_fulcio().url == f"http://{stack.host('fulcio')}:5555"
    assert len(trust.signing_config.get_tlogs()) == 1
    assert trust.signing_config.get_oidc_url() == "http://issuer.invalid:8080"
    assert len(list(trust.trusted_root.get_fulcio_certs())) == 1


def test_a_token_names_the_identity_and_the_issuer_fulcio_trusts(tmp_path: Path) -> None:
    local = written(tmp_path)

    token = IdentityToken(local.token())

    assert token.identity == IDENTITY
    assert token.issuer == local.issuer


def test_a_test_finds_the_run_s_sigstore_by_its_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = written(tmp_path)
    descriptor = tmp_path / "sigstore.json"
    descriptor.write_text(local.model_dump_json())
    monkeypatch.setenv(SIGSTORE_VARIABLE, str(descriptor))

    assert local_sigstore() == local

    monkeypatch.delenv(SIGSTORE_VARIABLE)
    with pytest.raises(RuntimeError, match="--sigstore"):
        local_sigstore()

"""A sealed REE is signed beside its seal: a Sigstore bundle over its digest, added once, carried with it."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from signed_bundles import signed_bundle, statement_of

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import (
    LoadReeBundleArgs,
    LoadReeBundleCommand,
    SealReeArgs,
    SealReeCommand,
    SignReeArgs,
    SignReeCommand,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.signature import PREDICATE_TYPES, signature_path

AUTHOR_APPROVAL = signature_path("author_approval")


def bundle(digest: str, predicate_type: str = PREDICATE_TYPES["author_approval"]) -> bytes:
    content: bytes = signed_bundle(statement_of(digest, predicate_type))
    return content


def initialized(tmp_path: Path, name: str = "author") -> ReeLayout:
    layout = ReeLayout(root=tmp_path / name)
    initialize_ree(layout, name=name)
    return layout


def sealed(tmp_path: Path) -> tuple[ReeLayout, str]:
    layout = initialized(tmp_path)
    args = SealReeArgs(source_included=False, experiment_environment_included=False, results_included=False)
    result = run_command(SealReeCommand(args=args), log=lambda *args: None, layout=layout)
    assert result.status == "succeeded", result
    seal = ReeDirectory(layout).read_ree().seal
    assert seal is not None
    return layout, str(seal.ree_digest)


def sign(layout: ReeLayout, content: bytes, slot: str = "signature") -> ActionResult:
    layout.upload_staging_file(slot).parent.mkdir(parents=True, exist_ok=True)
    layout.upload_staging_file(slot).write_bytes(content)
    args = SignReeArgs(upload_token=slot, archive_name="approval.sigstore.json")
    return run_command(SignReeCommand(args=args), log=lambda *args: None, layout=layout)


def test_a_sealed_ree_is_signed_beside_its_seal_and_the_signature_is_committed(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    before = layout.manifest.read_bytes()
    content = bundle(digest)
    signed = sign(layout, content)
    assert signed.status == "succeeded", signed
    assert signed.outputs == {"claim": "author_approval", "path": AUTHOR_APPROVAL, "ree_digest": digest}
    assert (layout.root / AUTHOR_APPROVAL).read_bytes() == content
    assert layout.manifest.read_bytes() == before
    assert not layout.upload_staging_file("signature").exists()
    assert signed.history is not None
    commit = signed.history.after_snapshot_id
    assert commit is not None
    with open_history(layout) as history:
        committed = history.git("show", f"{commit}:{AUTHOR_APPROVAL}").stdout
        changed = history.git("show", "--name-only", "--format=", commit).stdout
    assert committed == content
    assert changed.decode().split() == [AUTHOR_APPROVAL]


def test_only_a_sealed_ree_is_signed(tmp_path: Path) -> None:
    layout = initialized(tmp_path)
    refused = sign(layout, bundle("sha256:" + "0" * 64))
    assert refused.status == "failed"
    assert not (layout.root / AUTHOR_APPROVAL).exists()


def test_a_signature_over_another_digest_or_claim_or_no_statement_is_refused(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    for content in (
        bundle("sha256:" + "0" * 64),
        bundle(digest, "https://example.org/another-claim"),
        b'{"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"}',
    ):
        refused = sign(layout, content)
        assert refused.status == "failed", content
    assert not (layout.root / AUTHOR_APPROVAL).exists()


def test_a_claim_is_signed_once(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    first = bundle(digest)
    assert sign(layout, first).status == "succeeded"
    again = sign(layout, bundle(digest), slot="again")
    assert again.status == "failed"
    assert (layout.root / AUTHOR_APPROVAL).read_bytes() == first


def test_a_signature_its_certificate_s_key_did_not_make_is_refused_and_leaves_the_claim_open(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    statement = statement_of(digest, PREDICATE_TYPES["author_approval"])
    other = statement_of("sha256:" + "0" * 64, PREDICATE_TYPES["author_approval"])
    for content in (
        signed_bundle(statement, holder=ec.generate_private_key(ec.SECP256R1())),
        signed_bundle(other, carried=statement),
    ):
        refused = sign(layout, content)
        assert refused.failure is not None
        assert refused.failure.category == "validation"
        assert "not signed by the key its certificate holds" in refused.failure.message
        assert not (layout.root / AUTHOR_APPROVAL).exists()
    assert sign(layout, bundle(digest)).status == "succeeded", "a refused signature takes no claim"


@pytest.mark.parametrize(
    ("material", "message"),
    [({}, "holds no certificate"), ({"certificate": {"rawBytes": "MA=="}}, "not DER X.509")],
)
def test_a_bundle_without_a_certificate_to_verify_by_is_refused(
    tmp_path: Path, material: dict[str, object], message: str
) -> None:
    layout, digest = sealed(tmp_path)
    content = json.loads(bundle(digest))
    content["verificationMaterial"] = material
    refused = sign(layout, json.dumps(content).encode())
    assert refused.failure is not None
    assert message in refused.failure.message
    assert not (layout.root / AUTHOR_APPROVAL).exists()


def test_a_signed_ree_exports_and_loads_with_its_signature(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    content = bundle(digest)
    assert sign(layout, content).status == "succeeded"
    with materialized_ree_download(layout) as archive:
        data = archive.read_bytes()
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.read(f"ree/{AUTHOR_APPROVAL}") == content
    destination = initialized(tmp_path, "destination")
    destination.upload_staging_file("bundle").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(args=LoadReeBundleArgs(upload_token="bundle", archive_name="ree.zip")),  # noqa: S106
        log=lambda *args: None,
        layout=destination,
    )
    assert loaded.status == "succeeded", loaded
    assert (destination.root / AUTHOR_APPROVAL).read_bytes() == content
    seal = ReeDirectory(destination).read_ree().seal
    assert seal is not None
    assert str(seal.ree_digest) == digest


def test_the_same_signature_given_again_is_nothing_to_do(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    signature = bundle(digest)
    assert sign(layout, signature).status == "succeeded"

    assert sign(layout, signature, slot="again").status == "succeeded"
    assert not layout.upload_staging_file("again").exists()


def test_a_seal_asked_for_again_as_it_was_made_answers_with_that_seal(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    args = SealReeArgs(source_included=False, experiment_environment_included=False, results_included=False)

    again = run_command(SealReeCommand(args=args), log=lambda *a: None, layout=layout)

    assert again.status == "succeeded"
    assert again.outputs["ree_digest"] == digest
    seal = ReeDirectory(layout).read_ree().seal
    assert seal is not None
    assert str(seal.ree_digest) == digest

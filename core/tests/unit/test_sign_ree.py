"""A sealed REE is signed beside its seal: a Sigstore bundle over its digest, added once, carried with it."""

from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

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
    algorithm, _, value = digest.partition(":")
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "ree", "digest": {algorithm: value}}],
        "predicateType": predicate_type,
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
    signed = sign(layout, bundle(digest))
    assert signed.status == "succeeded", signed
    assert signed.outputs == {"claim": "author_approval", "path": AUTHOR_APPROVAL, "ree_digest": digest}
    assert (layout.root / AUTHOR_APPROVAL).read_bytes() == bundle(digest)
    assert layout.manifest.read_bytes() == before
    assert not layout.upload_staging_file("signature").exists()
    assert signed.history is not None
    commit = signed.history.after_snapshot_id
    assert commit is not None
    with open_history(layout) as history:
        committed = history.git("show", f"{commit}:{AUTHOR_APPROVAL}").stdout
        changed = history.git("show", "--name-only", "--format=", commit).stdout
    assert committed == bundle(digest)
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
    assert sign(layout, bundle(digest)).status == "succeeded"
    again = sign(layout, bundle(digest), slot="again")
    assert again.status == "failed"
    assert (layout.root / AUTHOR_APPROVAL).read_bytes() == bundle(digest)


def test_a_signed_ree_exports_and_loads_with_its_signature(tmp_path: Path) -> None:
    layout, digest = sealed(tmp_path)
    assert sign(layout, bundle(digest)).status == "succeeded"
    with materialized_ree_download(layout) as archive:
        data = archive.read_bytes()
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.read(f"ree/{AUTHOR_APPROVAL}") == bundle(digest)
    destination = initialized(tmp_path, "destination")
    destination.upload_staging_file("bundle").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(args=LoadReeBundleArgs(upload_token="bundle", archive_name="ree.zip")),  # noqa: S106
        log=lambda *args: None,
        layout=destination,
    )
    assert loaded.status == "succeeded", loaded
    assert (destination.root / AUTHOR_APPROVAL).read_bytes() == bundle(digest)
    seal = ReeDirectory(destination).read_ree().seal
    assert seal is not None
    assert str(seal.ree_digest) == digest

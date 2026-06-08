"""Tests for receipt journaling: redaction, snapshotting, two-phase open/close, I/O."""

from __future__ import annotations

import json
import logging
import os

import pytest

from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.receipt_journal import ReceiptJournal
from repo2ree_executor.journal import (
    _OUTPUT_ELIDE_THRESHOLD_BYTES,
    elide_large_outputs,
    redact_command,
    snapshot_ree_digest,
)
from repo2ree_protocol.receipt import (
    ReceiptClose,
    ReceiptOpen,
    compute_action_digest,
)

_LOGGER = "repo2ree_core.storage.receipt_journal"

# ------------------------------------------------
# Fixtures / helpers
# ------------------------------------------------


def _open(receipt_id: str, operation: str = "write_file", **kw) -> ReceiptOpen:
    return ReceiptOpen(
        receipt_id=receipt_id,
        operation=operation,
        command={"operation": operation, "args": {}},
        action_digest="sha256:aabbcc",
        started_at="2026-01-01T00:00:00Z",
        **kw,
    )


def _close(receipt_id: str, status: str = "succeeded", **kw) -> ReceiptClose:
    return ReceiptClose(
        receipt_id=receipt_id,
        status=status,  # type: ignore[arg-type]
        finished_at="2026-01-01T00:00:01Z",
        **kw,
    )


def _write_pair(layout: ReeLayout, rid: str, **close_kw) -> None:
    j = ReceiptJournal(layout)
    j.append_open(_open(rid))
    j.append_close(_close(rid, **close_kw))


def _write_file_command(content: str) -> dict:
    return {"operation": "write_file", "args": {"path": "a.txt", "content": content}}


def _upload_command(token: str) -> dict:
    return {
        "operation": "extract_upload",
        "args": {"upload_token": token, "archive_name": "src.zip"},
    }


# ================================================
# Redaction
# ================================================


def test_redaction_returns_a_distinct_copy():
    cmd = _write_file_command("x" * 100_000)
    redacted = redact_command(cmd)
    assert redacted is not cmd
    assert cmd["args"]["content"] == "x" * 100_000
    assert compute_action_digest(cmd) != compute_action_digest(redacted)


def test_redaction_elides_content():
    content = "hello world\n" * 1000
    redacted = redact_command(_write_file_command(content))
    elided = redacted["args"]["content"]
    assert elided["__elided__"] is True
    assert elided["bytes"] == len(content.encode())
    assert elided["sha256"].startswith("sha256:")
    assert len(json.dumps(redacted)) < len(content)


def test_redaction_elides_upload_token():
    cmd = _upload_command("tok-abc123")
    redacted = redact_command(cmd)
    elided = redacted["args"]["upload_token"]
    assert elided["__elided__"] is True
    assert elided["sha256"].startswith("sha256:")
    assert redacted["args"]["archive_name"] == "src.zip"


def test_redaction_leaves_commands_without_elided_args_untouched():
    cmd = {"operation": "delete_file", "args": {"path": "a.txt"}}
    assert redact_command(cmd) == cmd


# ================================================
# REE state snapshotting
# ================================================


def test_snapshot_ree_digest_returns_reetree_prefix(tmp_path):
    layout = ReeLayout(root=tmp_path)
    assert snapshot_ree_digest(layout).startswith("reetree-v1:")


def test_snapshot_ree_digest_stable_across_reads(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    (layout.overlay / "a.txt").write_text("hello")
    assert snapshot_ree_digest(layout) == snapshot_ree_digest(layout)


def test_snapshot_ree_digest_changes_when_overlay_content_changes(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    f = layout.overlay / "file.txt"
    f.write_text("version 1")
    d1 = snapshot_ree_digest(layout)
    f.write_text("version 2")
    d2 = snapshot_ree_digest(layout)
    assert d1 != d2


def test_snapshot_ree_digest_changes_when_file_mode_changes(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    f = layout.overlay / "run.sh"
    f.write_text("#!/bin/sh\necho hello\n")
    f.chmod(0o644)
    d1 = snapshot_ree_digest(layout)
    f.chmod(0o755)
    d2 = snapshot_ree_digest(layout)
    assert d1 != d2


def test_snapshot_ree_digest_captures_symlink(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    (layout.overlay / "real.txt").write_text("real")
    os.symlink("real.txt", layout.overlay / "link.txt")
    d_with_link = snapshot_ree_digest(layout)
    os.unlink(layout.overlay / "link.txt")
    d_without_link = snapshot_ree_digest(layout)
    assert d_with_link != d_without_link


def test_snapshot_ree_digest_captures_empty_directory(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    d1 = snapshot_ree_digest(layout)
    (layout.overlay / "emptydir").mkdir()
    d2 = snapshot_ree_digest(layout)
    assert d1 != d2


def test_snapshot_ree_digest_changes_when_upstream_changes(tmp_path):
    layout = ReeLayout(root=tmp_path)
    d1 = snapshot_ree_digest(layout)
    layout.snapshot_archive.write_bytes(b"fake archive v1")
    d2 = snapshot_ree_digest(layout)
    layout.snapshot_archive.write_bytes(b"fake archive v2")
    d3 = snapshot_ree_digest(layout)
    assert d1 != d2
    assert d2 != d3


def test_snapshot_ree_digest_changes_when_intent_changes(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.metadata.write_text(
        json.dumps({"reeIntent": {"name": "my-ree", "runtime": "Dockerfile"}}),
        encoding="utf-8",
    )
    d1 = snapshot_ree_digest(layout)
    layout.metadata.write_text(
        json.dumps({"reeIntent": {"name": "my-ree", "runtime": "Dockerfile.v2"}}),
        encoding="utf-8",
    )
    d2 = snapshot_ree_digest(layout)
    assert d1 != d2


def test_snapshot_ree_digest_empty_ree_is_stable(tmp_path):
    # A completely empty REE (no source, no overlay, no intent) still produces
    # a stable, deterministic digest.
    layout = ReeLayout(root=tmp_path)
    assert snapshot_ree_digest(layout) == snapshot_ree_digest(layout)


# ================================================
# Output elision
# ================================================


def test_elide_large_outputs_elides_string_over_threshold():
    big = "x" * (_OUTPUT_ELIDE_THRESHOLD_BYTES + 1)
    result = elide_large_outputs({"data": big})
    stub = result["data"]
    assert stub["__elided__"] is True
    assert stub["bytes"] == len(big.encode())
    assert stub["sha256"].startswith("sha256:")


def test_elide_large_outputs_keeps_small_strings():
    small = "x" * _OUTPUT_ELIDE_THRESHOLD_BYTES
    assert elide_large_outputs({"data": small}) == {"data": small}


def test_elide_large_outputs_leaves_non_string_values():
    outputs = {"count": 42, "flag": True, "nested": {"a": 1}}
    assert elide_large_outputs(outputs) == outputs


def test_elide_large_outputs_returns_distinct_copy():
    original = {"a": "small"}
    result = elide_large_outputs(original)
    assert result is not original


# ================================================
# ReceiptJournal — append and read round-trip
# ================================================


def test_append_open_creates_receipts_dir(tmp_path):
    layout = ReeLayout(root=tmp_path)
    ReceiptJournal(layout).append_open(_open("r1"))
    assert layout.receipts_journal.exists()


def test_read_all_returns_empty_when_no_journal(tmp_path):
    assert ReceiptJournal(ReeLayout(root=tmp_path)).read_all() == []


def test_read_all_assembles_open_close_pair(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    receipts = ReceiptJournal(layout).read_all()
    assert len(receipts) == 1
    r = receipts[0]
    assert r.receipt_id == "r1"
    assert r.operation == "write_file"
    assert r.status == "succeeded"


def test_read_all_threads_output_digest(tmp_path):
    layout = ReeLayout(root=tmp_path)
    j = ReceiptJournal(layout)
    j.append_open(_open("r1"))
    j.append_close(
        ReceiptClose(
            receipt_id="r1",
            status="succeeded",
            finished_at="2026-01-01T00:00:01Z",
            output_digest="reetree-v1:abcdef01",
        )
    )
    receipts = j.read_all()
    assert receipts[0].output_digest == "reetree-v1:abcdef01"


def test_read_all_output_digest_none_when_absent(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    receipts = ReceiptJournal(layout).read_all()
    assert receipts[0].output_digest is None


def test_read_all_preserves_open_order(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    _write_pair(layout, "r2")
    _write_pair(layout, "r3")
    ids = [r.receipt_id for r in ReceiptJournal(layout).read_all()]
    assert ids == ["r1", "r2", "r3"]


def test_read_all_omits_dangling_open_and_warns(tmp_path, caplog):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    ReceiptJournal(layout).append_open(_open("r2"))  # no close
    _write_pair(layout, "r3")
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        receipts = ReceiptJournal(layout).read_all()
    ids = [r.receipt_id for r in receipts]
    assert ids == ["r1", "r3"]
    assert "dangling" in caplog.text


def test_read_all_skips_corrupt_lines_and_warns(tmp_path, caplog):
    layout = ReeLayout(root=tmp_path)
    layout.receipts.mkdir()
    layout.receipts_journal.write_text(
        _open("r1").model_dump_json()
        + "\n"
        + "{corrupt\n"
        + _close("r1").model_dump_json()
        + "\n"
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        receipts = ReceiptJournal(layout).read_all()
    assert len(receipts) == 1
    assert "corrupt" in caplog.text


@pytest.mark.parametrize("corrupt_count", [0, 2])
def test_read_all_warns_only_when_there_are_corrupt_lines(
    tmp_path, caplog, corrupt_count
):
    layout = ReeLayout(root=tmp_path)
    layout.receipts.mkdir()
    content = (
        _open("r1").model_dump_json()
        + "\n"
        + _close("r1").model_dump_json()
        + "\n"
        + "{bad\n" * corrupt_count
    )
    layout.receipts_journal.write_text(content)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        ReceiptJournal(layout).read_all()
    assert ("corrupt" in caplog.text) == (corrupt_count > 0)


# ================================================
# ReceiptJournal — last_receipt_id (predecessor chaining)
# ================================================


def test_last_receipt_id_returns_none_when_journal_missing(tmp_path):
    assert ReceiptJournal(ReeLayout(root=tmp_path)).last_receipt_id() is None


def test_last_receipt_id_returns_none_when_journal_empty(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.receipts.mkdir()
    layout.receipts_journal.write_text("")
    assert ReceiptJournal(layout).last_receipt_id() is None


def test_last_receipt_id_returns_last_close_id(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    _write_pair(layout, "r2")
    assert ReceiptJournal(layout).last_receipt_id() == "r2"


def test_last_receipt_id_ignores_dangling_open(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    ReceiptJournal(layout).append_open(_open("r2"))  # dangling
    # last_receipt_id should still point to r1 (the last *close*)
    assert ReceiptJournal(layout).last_receipt_id() == "r1"


def test_last_receipt_id_skips_corrupt_lines_and_warns(tmp_path, caplog):
    layout = ReeLayout(root=tmp_path)
    layout.receipts.mkdir()
    layout.receipts_journal.write_text(
        _open("r1").model_dump_json()
        + "\n"
        + _close("r1").model_dump_json()
        + "\n"
        + "{torn\n"
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        rid = ReceiptJournal(layout).last_receipt_id()
    assert rid == "r1"
    assert "scanned" in caplog.text or "skipped" in caplog.text


# ================================================
# ReceiptJournal — dangling_open
# ================================================


def test_dangling_open_returns_none_when_all_closed(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    assert ReceiptJournal(layout).dangling_open() is None


def test_dangling_open_returns_open_receipt(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    ReceiptJournal(layout).append_open(_open("r2"))
    dangling = ReceiptJournal(layout).dangling_open()
    assert dangling is not None
    assert dangling.receipt_id == "r2"


def test_dangling_open_carries_input_digest(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    (layout.overlay / "f.txt").write_text("hello")
    digest = snapshot_ree_digest(layout)
    ReceiptJournal(layout).append_open(_open("r1", input_digest=digest))
    dangling = ReceiptJournal(layout).dangling_open()
    assert dangling is not None
    assert dangling.input_digest == digest


# ================================================
# Dangling-open recovery helpers
# ================================================


def _recover_dangling(layout: ReeLayout) -> str | None:
    """Mirror the recovery logic from cli.py for use in tests.

    Returns the recovery_note written ("no_effect_detected" or "state_changed"),
    or None if there was nothing to recover.
    """
    journal = ReceiptJournal(layout)
    dangling = journal.dangling_open()
    if dangling is None:
        return None
    current_digest = snapshot_ree_digest(layout)
    recovery_note = (
        "no_effect_detected"
        if dangling.input_digest == current_digest
        else "state_changed"
    )
    journal.append_close(
        ReceiptClose(
            receipt_id=dangling.receipt_id,
            status="failed",
            exit_code=1,
            outputs={"recovery": recovery_note},
            finished_at="2026-01-01T00:01:00Z",
            output_digest=current_digest,
        )
    )
    return recovery_note


def test_recovery_no_effect_detected_when_state_unchanged(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    (layout.overlay / "f.txt").write_text("hello")
    digest = snapshot_ree_digest(layout)
    ReceiptJournal(layout).append_open(_open("r1", input_digest=digest))

    note = _recover_dangling(layout)

    assert note == "no_effect_detected"
    assert ReceiptJournal(layout).dangling_open() is None
    receipts = ReceiptJournal(layout).read_all()
    assert len(receipts) == 1
    assert receipts[0].status == "failed"
    assert receipts[0].outputs == {"recovery": "no_effect_detected"}


def test_recovery_state_changed_when_overlay_mutated(tmp_path):
    layout = ReeLayout(root=tmp_path)
    layout.overlay.mkdir(parents=True)
    (layout.overlay / "f.txt").write_text("before")
    digest_before = snapshot_ree_digest(layout)
    ReceiptJournal(layout).append_open(_open("r1", input_digest=digest_before))

    # Simulate action side-effect applied before crash
    (layout.overlay / "f.txt").write_text("after")

    note = _recover_dangling(layout)

    assert note == "state_changed"
    assert ReceiptJournal(layout).dangling_open() is None
    receipts = ReceiptJournal(layout).read_all()
    assert receipts[0].outputs == {"recovery": "state_changed"}


def test_recovery_leaves_output_digest_on_close(tmp_path):
    layout = ReeLayout(root=tmp_path)
    ReceiptJournal(layout).append_open(
        _open("r1", input_digest=snapshot_ree_digest(layout))
    )
    _recover_dangling(layout)
    receipts = ReceiptJournal(layout).read_all()
    assert receipts[0].output_digest is not None
    assert receipts[0].output_digest.startswith("reetree-v1:")


def test_recovery_close_becomes_predecessor_of_next_receipt(tmp_path):
    layout = ReeLayout(root=tmp_path)
    ReceiptJournal(layout).append_open(
        _open("r1", input_digest=snapshot_ree_digest(layout))
    )
    _recover_dangling(layout)

    # Simulate the next action being written after recovery
    j = ReceiptJournal(layout)
    j.append_open(_open("r2", predecessor=j.last_receipt_id()))
    j.append_close(_close("r2"))

    receipts = ReceiptJournal(layout).read_all()
    assert receipts[1].predecessor == "r1"


def test_recovery_noop_when_no_dangling_open(tmp_path):
    layout = ReeLayout(root=tmp_path)
    _write_pair(layout, "r1")
    assert _recover_dangling(layout) is None
    assert len(ReceiptJournal(layout).read_all()) == 1

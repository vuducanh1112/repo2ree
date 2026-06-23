from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.workspace.manifest import build_draft_manifest_payload, build_manifest_payload


def _intent(**overrides) -> ReeIntent:
    return ReeIntent(name="demo").apply_patch(overrides)


def _session(**overrides) -> ReeSession:
    return ReeSession(**overrides)


def test_intent_name_used_in_manifest():
    manifest = build_manifest_payload(_intent(name="from-intent"), _session(), ree_id="abc")
    assert manifest["name"] == "from-intent"


def test_falls_back_to_ree_id_prefix_when_no_names():
    manifest = build_manifest_payload(ReeIntent(name=""), _session(), ree_id="abcdef0123456789")
    assert manifest["name"] == "workspace-abcdef01"


def test_origin_url_comes_from_intent():
    manifest = build_manifest_payload(
        _intent(origin_url="https://example.com/repo.git"),
        _session(),
        ree_id="abc",
    )
    assert manifest["origin_url"] == "https://example.com/repo.git"


def test_source_type_comes_from_intent():
    manifest = build_manifest_payload(_intent(source_type="git"), _session(), ree_id="abc")
    assert manifest["source_type"] == "git"


def test_named_slot_paths_are_normalized():
    intent = _intent(
        runtime="/runtime.tar.gz",
        sbom="  sbom.json  ",
        build_runtime_script="/scripts/build.sh",
    )
    manifest = build_manifest_payload(intent, _session(), ree_id="abc")
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "sbom.json"
    assert manifest["build_runtime_script"] == "scripts/build.sh"


def test_activation_and_runtime_entry_in_manifest():
    manifest = build_manifest_payload(_intent(), _session(), ree_id="abc")
    # Activation is a required singleton; the runtime entry defaults to docker.
    assert manifest["activation"] == ReeIntent().activation.model_dump()
    assert manifest["runtime_entry"]["kind"] == "container"
    assert manifest["runtime_entry"]["engine"] == "docker"


def test_pure_no_filesystem_dependency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    intent = _intent(runtime="r")
    a = build_manifest_payload(intent, _session(), ree_id="abc")
    b = build_manifest_payload(intent, _session(), ree_id="abc")
    assert a == b


def test_packaging_reflected_in_manifest_via_session():
    session = ReeSession(source_included=True, runtime_included=True)
    manifest = build_manifest_payload(_intent(), session, ree_id="abc")
    assert manifest["source_included"] is True
    assert manifest["runtime_included"] is True


def test_session_fields_reflected_in_manifest():
    session = ReeSession(
        dependency_level=3,
        environment_level=2,
        source_available=True,
        source_acquired_by="download",
    )
    manifest = build_manifest_payload(_intent(), session, ree_id="abc")
    assert manifest["dependency_level"] == 3
    assert manifest["environment_level"] == 2
    assert manifest["source_available"] is True
    assert manifest["source_acquired_by"] == "download"


def test_draft_manifest_adds_workspace_context_without_file_content():
    metadata = {
        "reeId": "abc123",
        "name": "demo",
        "status": "ready",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "reeIntent": _intent(runtime="runtime.tar.gz").model_dump(exclude_none=True),
        "reeSession": _session(source_available=True).model_dump(exclude_none=True),
    }

    manifest = build_draft_manifest_payload(
        metadata,
        workspace_files=[
            {
                "path": "main.py",
                "kind": "source",
                "size": 12,
                "content": "print('hi')",
            }
        ],
        ree_files=[
            {
                "path": "overlay/build.sh",
                "kind": "ree",
                "tag": "Overlay",
                "size": 8,
            },
            {
                "path": "artifacts/runtime.tar.gz",
                "kind": "ree",
                "tag": "Artifact",
                "size": 99,
                "content": None,
            },
        ],
    )

    assert manifest["manifest_state"] == "draft"
    assert manifest["ree_id"] == "abc123"
    assert manifest["status"] == "ready"
    assert manifest["updated_at"] == "2026-01-02T00:00:00Z"
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["source_available"] is True
    assert manifest["file_inventory"] == {
        "workspace": [{"path": "main.py", "kind": "source", "size": 12}],
        "overlay": [{"path": "overlay/build.sh", "kind": "ree", "tag": "Overlay", "size": 8}],
        "artifacts": [
            {
                "path": "artifacts/runtime.tar.gz",
                "kind": "ree",
                "tag": "Artifact",
                "size": 99,
            }
        ],
    }

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.workspace.manifest import build_manifest_payload


def _intent(**overrides) -> ReeIntent:
    return ReeIntent(name="demo").apply_patch(overrides)


def _session(**overrides) -> ReeSession:
    return ReeSession(**overrides)


def test_metadata_name_overrides_intent_name():
    manifest = build_manifest_payload(
        {"name": "from-metadata"}, _intent(), _session(), ree_id="abc"
    )
    assert manifest["name"] == "from-metadata"


def test_falls_back_to_ree_id_prefix_when_no_names():
    manifest = build_manifest_payload(
        {}, ReeIntent(name=""), _session(), ree_id="abcdef0123456789"
    )
    assert manifest["name"] == "workspace-abcdef01"


def test_metadata_external_ref_overrides_origin_url():
    manifest = build_manifest_payload(
        {"externalRef": "https://example.com/repo.git"},
        _intent(),
        _session(),
        ree_id="abc",
    )
    assert manifest["origin_url"] == "https://example.com/repo.git"


def test_source_type_pulled_from_source_metadata_dict():
    manifest = build_manifest_payload(
        {"source": {"sourceType": "git"}}, _intent(), _session(), ree_id="abc"
    )
    assert manifest["source_type"] == "git"


def test_source_type_falls_back_when_source_is_none():
    manifest = build_manifest_payload(
        {"source": None}, _intent(source_type="tarball"), _session(), ree_id="abc"
    )
    assert manifest["source_type"] == "tarball"


def test_named_slot_paths_are_normalized():
    intent = _intent(
        runtime="/runtime.tar.gz",
        sbom="  sbom.json  ",
        build_runtime_script="/scripts/build.sh",
        activation_script="",
    )
    manifest = build_manifest_payload({}, intent, _session(), ree_id="abc")
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "sbom.json"
    assert manifest["build_script"] == "scripts/build.sh"
    assert manifest["activation_script"] is None


def test_pure_no_filesystem_dependency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    intent = _intent(runtime="r")
    a = build_manifest_payload({"name": "x"}, intent, _session(), ree_id="abc")
    b = build_manifest_payload({"name": "x"}, intent, _session(), ree_id="abc")
    assert a == b


def test_packaging_policy_reflected_in_manifest():
    from repo2ree_core.domain.ree_intent import PackagingPolicy

    intent = ReeIntent(
        name="demo",
        packaging=PackagingPolicy(source_included=True, runtime_included=True),
    )
    manifest = build_manifest_payload({}, intent, _session(), ree_id="abc")
    assert manifest["source_included"] is True
    assert manifest["runtime_included"] is True


def test_session_fields_reflected_in_manifest():
    session = ReeSession(
        dependency_level=3,
        environment_level=2,
        source_available=True,
        source_acquired_by="download",
    )
    manifest = build_manifest_payload({}, _intent(), session, ree_id="abc")
    assert manifest["dependency_level"] == 3
    assert manifest["environment_level"] == 2
    assert manifest["source_available"] is True
    assert manifest["source_acquired_by"] == "download"

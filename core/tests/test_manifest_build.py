from repo2ree_core.domain.ree import REE
from repo2ree_core.workspace.manifest import build_manifest_payload


def _patched_ree(**overrides) -> REE:
    return REE(name="demo").apply_patch(overrides)


def test_metadata_name_overrides_ree_name():
    ree = _patched_ree()
    manifest = build_manifest_payload({"name": "from-metadata"}, ree, ree_id="abc")
    assert manifest["name"] == "from-metadata"


def test_falls_back_to_ree_id_prefix_when_no_names():
    ree = REE(name="")
    manifest = build_manifest_payload({}, ree, ree_id="abcdef0123456789")
    assert manifest["name"] == "workspace-abcdef01"


def test_metadata_external_ref_overrides_origin_url():
    ree = _patched_ree()
    manifest = build_manifest_payload(
        {"externalRef": "https://example.com/repo.git"}, ree, ree_id="abc"
    )
    assert manifest["origin_url"] == "https://example.com/repo.git"


def test_source_type_pulled_from_source_metadata_dict():
    ree = _patched_ree()
    manifest = build_manifest_payload(
        {"source": {"sourceType": "git"}}, ree, ree_id="abc"
    )
    assert manifest["source_type"] == "git"


def test_source_type_falls_back_when_source_is_none():
    ree = _patched_ree(source_type="tarball")
    manifest = build_manifest_payload({"source": None}, ree, ree_id="abc")
    assert manifest["source_type"] == "tarball"


def test_named_slot_paths_are_normalized():
    ree = _patched_ree(
        runtime="/runtime.tar.gz",
        sbom="  sbom.json  ",
        build_runtime_script="/scripts/build.sh",
        activation_script="",
    )
    manifest = build_manifest_payload({}, ree, ree_id="abc")
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "sbom.json"
    assert manifest["build_script"] == "scripts/build.sh"
    assert manifest["activation_script"] is None


def test_pure_no_filesystem_dependency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ree = _patched_ree(runtime="r")
    a = build_manifest_payload({"name": "x"}, ree, ree_id="abc")
    b = build_manifest_payload({"name": "x"}, ree, ree_id="abc")
    assert a == b

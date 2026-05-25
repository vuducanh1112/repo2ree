import json

from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.workspace_ops import (
    create_workspace,
    patch_workspace,
    remove_source,
)


def test_remove_source_resets_evaluate_state_and_deletes_report(tmp_path):
    workspace = create_workspace(tmp_path, source_mode="demo", name="evaluate-reset")
    ree_id = workspace["reeId"]
    layout = ReeLayout.for_ree(tmp_path, ree_id)

    patch_workspace(
        tmp_path,
        ree_id,
        {
            "origin_url": "https://example.org/repo.git",
            "source_type": "git",
            "runtime": "runtime.tar.gz",
            "build_runtime_script": "build.sh",
            "activation_script": "activate.sh",
            "sbom": "sbom.json",
            "source_included": True,
            "runtime_included": True,
            "dependency_level": 3,
            "environment_level": 2,
            "machine_level": 1,
            "detected_dependencies": "4 dependencies",
        },
    )

    report_path = layout.artifact_file("reproducibility-report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"dependencyLevel": 3}), encoding="utf-8")

    result = remove_source(tmp_path, ree_id)

    ree_draft = result["workspace"]["reeDraft"]
    assert result["invalidatedSteps"] == ["source", "evaluate", "workflow"]
    assert ree_draft["dependency_level"] == 0
    assert ree_draft["environment_level"] == 0
    assert ree_draft["machine_level"] == 0
    assert "detected_dependencies" not in ree_draft
    assert ree_draft["runtime"] == ""
    assert ree_draft["sbom"] == ""
    assert not report_path.exists()

"""Script report responses remain valid when real dispatch captures history."""

import pytest

from repo2ree_api.deps import workbench_manager
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history


@pytest.mark.parametrize("endpoint", ["script-inferences:generate", "script-lints:run"])
def test_script_report_excludes_capture_metadata(client, online_ree, monkeypatch, tmp_path, endpoint):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="reports")
    layout.upstream.mkdir(exist_ok=True)
    (layout.upstream / "Dockerfile").write_text("FROM python:3.13-slim\n")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    outputs = {}

    def dispatch(handle, command, run_id, log):
        result = run_command(command, run_id=run_id, log=log)
        assert result.history is not None
        assert result.history.capture_status == "captured"
        outputs.update(result.model_dump(mode="json")["outputs"])
        return result

    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch)
    response = client.post(f"/api/v1/rees/{online_ree.ree_id}/{endpoint}", json={"targets": [{"kind": "build"}]})

    assert response.status_code == 200, response.text
    assert "history" not in outputs
    assert response.json() == {key: value for key, value in outputs.items() if key != "history"}
    assert len(read_operation_history(layout).operations) == 1
    if endpoint == "script-inferences:generate":
        assert response.json()["dags"]
        assert response.json()["results"][0]["status"] == "complete"

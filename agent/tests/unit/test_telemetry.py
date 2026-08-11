from repo2ree_agent.telemetry import workbench_reference_hash
from repo2ree_protocol.agent import WorkbenchRef


def test_workbench_reference_hash_is_stable_and_hides_token() -> None:
    ref = WorkbenchRef(runtime="docker", token="private-runtime-payload")  # noqa: S106

    fingerprint = workbench_reference_hash(ref)

    assert fingerprint == workbench_reference_hash(ref)
    assert len(fingerprint) == 16
    assert ref.token not in fingerprint
    assert fingerprint != workbench_reference_hash(ref.model_copy(update={"runtime": "slurm"}))

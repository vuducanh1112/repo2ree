"""The evidence graph reads core's audit rules by their conventions; a change there must not thin it silently."""

from repo2ree_repoview.diagrams import evidence


def test_every_audited_step_is_audited_against_something() -> None:
    edges = evidence.collect()
    steps = {edge.step for edge in edges}
    found = {
        "experiment" if step == "experiments" else step for step, _ in evidence.AuditExtractor(evidence.AUDIT).steps()
    }

    assert found, "no _audit_*_step functions found in the audit rules"
    assert found == steps, f"steps the graph shows no edge into: {sorted(found - steps)}"


def test_every_receipt_compared_against_is_a_step_of_the_graph() -> None:
    edges = evidence.collect()
    steps = {edge.step for edge in edges}
    receipts = {edge.source.node for edge in edges if edge.source.kind == "receipt"}

    assert receipts, "no step is audited against another step's receipt"
    assert receipts <= steps, f"receipt slots with no step of that name; map them in SLOT_TO_STEP: {receipts - steps}"

"""Who may dial in as a directly installed workbench, and why one is refused.

The refusal string is operator-facing diagnostics, not a wire contract: the
close frame stays deliberately generic because the peer is unauthenticated.
What is asserted here is that each distinct cause is *distinguishable in the
server log* — an unset ``EXTERNAL_WORKBENCH_TOKEN`` and a mistyped one are the
same opaque 1008 to the workbench, and telling them apart from the client side
alone is not possible.
"""

from __future__ import annotations

from repo2ree_api.control.fleet import _external_refusal
from repo2ree_protocol.workbench import WorkbenchHello

_TOKEN = "operator-credential"  # noqa: S105 - a fixture value, not a credential


def _hello(**overrides: object) -> WorkbenchHello:
    fields: dict[str, object] = {
        "workbench_id": "wb-1",
        "mode": "external",
        "enrollment_token": _TOKEN,
    }
    return WorkbenchHello.model_validate(fields | overrides)


def test_a_matching_token_is_admitted() -> None:
    assert _external_refusal(_hello(), _TOKEN) is None


def test_an_unset_server_token_refuses_every_external_workbench() -> None:
    # The default. External registration is opt-in, so a control plane that was
    # never given the credential turns away even a correctly configured bench.
    refusal = _external_refusal(_hello(), "")

    assert refusal is not None
    assert "EXTERNAL_WORKBENCH_TOKEN is unset" in refusal


def test_a_mismatched_token_is_refused_and_says_so() -> None:
    mistyped = "not-the-credential"
    refusal = _external_refusal(_hello(enrollment_token=mistyped), _TOKEN)

    assert refusal is not None
    assert "does not match" in refusal


def test_an_empty_workbench_token_never_matches_an_unset_server_token() -> None:
    # Both sides blank must not read as agreement — that would admit anonymous
    # workbenches to any control plane that forgot to configure the credential.
    assert _external_refusal(_hello(enrollment_token=""), "") is not None


def test_an_allocation_id_belongs_to_a_managed_workbench_only() -> None:
    # A bench holding an allocation is provider-created and must come through
    # enrollment; presenting the operator credential instead cannot bypass it.
    refusal = _external_refusal(_hello(allocation_id="alloc-1"), _TOKEN)

    assert refusal is not None
    assert "allocation id" in refusal

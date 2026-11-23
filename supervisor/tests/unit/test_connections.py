from __future__ import annotations

import pytest

from repo2ree_protocol.queries import InitRee
from repo2ree_protocol.workbench import InitReeRequest, WorkbenchHello
from repo2ree_supervisor import WorkbenchConnection, WorkbenchConnectionRegistry, WorkbenchUnavailableError


def _connection(hello: WorkbenchHello | None) -> WorkbenchConnection:
    return WorkbenchConnection(send_text=lambda _text: None, hello=hello)


def test_list_workbenches_reports_hello_fields_sorted() -> None:
    registry = WorkbenchConnectionRegistry()
    registry.register(
        "z-workbench",
        _connection(
            WorkbenchHello(
                workbench_id="z-workbench",
                hostname="worker-b",
                version="0.1.0",
                store_id="lab-z",
            )
        ),
    )
    registry.register(
        "a-workbench",
        _connection(
            WorkbenchHello(
                workbench_id="a-workbench",
                hostname="worker-a",
                version="0.2.0",
                store_id="lab-a",
            )
        ),
    )

    infos = registry.list_workbenches()

    assert [i.workbench_id for i in infos] == ["a-workbench", "z-workbench"]
    first = infos[0]
    assert (first.hostname, first.version, first.store_id) == ("worker-a", "0.2.0", "lab-a")
    assert first.connected_at > 0


def test_list_workbenches_tolerates_missing_hello() -> None:
    registry = WorkbenchConnectionRegistry()
    registry.register("legacy", _connection(None))

    (info,) = registry.list_workbenches()

    assert info.workbench_id == "legacy"
    assert (info.hostname, info.version, info.store_id) == ("", "", "")


def test_unregister_drops_from_list() -> None:
    registry = WorkbenchConnectionRegistry()
    conn = _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1"))
    registry.register("a1", conn)
    registry.unregister("a1", conn)

    assert registry.list_workbenches() == []


def test_displacement_by_same_instance_logs_reconnect_not_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = WorkbenchConnectionRegistry()
    nonce = "abc123"
    registry.register("a1", _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1", nonce=nonce)))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.workbench_link"):
        registry.register("a1", _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1", nonce=nonce)))

    (record,) = caplog.records
    assert record.levelname == "INFO"
    assert "reconnected" in record.message


def test_displacement_by_different_instance_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1", nonce="instance-one")))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.workbench_link"):
        registry.register("a1", _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1", nonce="instance-two")))

    (record,) = caplog.records
    assert record.levelname == "WARNING"
    assert "different instance" in record.message


def test_displacement_without_nonces_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", _connection(None))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.workbench_link"):
        registry.register("a1", _connection(None))

    (record,) = caplog.records
    assert record.levelname == "WARNING"


def test_reconnect_displaces_old_connection_without_stale_eviction() -> None:
    registry = WorkbenchConnectionRegistry()
    old = _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1"))
    new = _connection(WorkbenchHello(workbench_id="a1", store_id="lab-1"))

    registry.register("a1", old)
    registry.register("a1", new)

    assert registry.pick("a1") is new
    with pytest.raises(WorkbenchUnavailableError, match="workbench connection closed"):
        next(old.request(InitReeRequest(ree_id="ree-1", init=InitRee(name="demo"))))

    registry.unregister("a1", old)
    assert registry.pick("a1") is new

    registry.unregister("a1", new)
    assert registry.list_workbenches() == []

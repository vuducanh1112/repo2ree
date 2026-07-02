"""The agent connection registry's fleet view (``list_agents``).

No real socket: connections are constructed with a no-op ``send_text`` and a
reported ``AgentHello``, then the registry is asked to describe them.
"""

from __future__ import annotations

import pytest

from repo2ree_protocol.agent import AgentHello, IsRunningRequest
from repo2ree_supervisor import AgentConnection, AgentConnectionRegistry, WorkbenchUnavailableError


def _connection(hello: AgentHello | None) -> AgentConnection:
    return AgentConnection(send_text=lambda _text: None, hello=hello)


def test_list_agents_reports_hello_fields_sorted() -> None:
    registry = AgentConnectionRegistry()
    registry.register(
        "z-agent",
        _connection(AgentHello(agent_id="z-agent", hostname="worker-b", version="0.1.0", docker_mode="dind")),
    )
    registry.register(
        "a-agent",
        _connection(AgentHello(agent_id="a-agent", hostname="worker-a", version="0.2.0", docker_mode="host-socket")),
    )

    infos = registry.list_agents()

    # Sorted by (hostname, agent_id): worker-a before worker-b.
    assert [i.agent_id for i in infos] == ["a-agent", "z-agent"]
    first = infos[0]
    assert (first.hostname, first.version, first.docker_mode) == ("worker-a", "0.2.0", "host-socket")
    assert first.connected_at > 0


def test_list_agents_tolerates_missing_hello() -> None:
    registry = AgentConnectionRegistry()
    registry.register("legacy", _connection(None))

    (info,) = registry.list_agents()

    assert info.agent_id == "legacy"
    assert (info.hostname, info.version, info.docker_mode) == ("", "", "")


def test_unregister_drops_from_list() -> None:
    registry = AgentConnectionRegistry()
    conn = _connection(AgentHello(agent_id="a1"))
    registry.register("a1", conn)
    registry.unregister("a1", conn)

    assert registry.list_agents() == []


def test_displacement_by_same_instance_logs_reconnect_not_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = AgentConnectionRegistry()
    nonce = "abc123"
    registry.register("a1", _connection(AgentHello(agent_id="a1", nonce=nonce)))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.ws"):
        registry.register("a1", _connection(AgentHello(agent_id="a1", nonce=nonce)))

    (record,) = caplog.records
    assert record.levelname == "INFO"
    assert "reconnected" in record.message


def test_displacement_by_different_instance_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    registry = AgentConnectionRegistry()
    registry.register("a1", _connection(AgentHello(agent_id="a1", nonce="instance-one")))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.ws"):
        registry.register("a1", _connection(AgentHello(agent_id="a1", nonce="instance-two")))

    (record,) = caplog.records
    assert record.levelname == "WARNING"
    assert "different instance" in record.message


def test_displacement_without_nonces_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    # No hello (or an empty nonce) can't prove it's the same instance, so the
    # registry stays loud rather than assuming a routine reconnect.
    registry = AgentConnectionRegistry()
    registry.register("a1", _connection(None))
    with caplog.at_level("INFO", logger="repo2ree_supervisor.ws"):
        registry.register("a1", _connection(None))

    (record,) = caplog.records
    assert record.levelname == "WARNING"


def test_reconnect_displaces_old_connection_without_stale_eviction() -> None:
    registry = AgentConnectionRegistry()
    old = _connection(AgentHello(agent_id="a1"))
    new = _connection(AgentHello(agent_id="a1"))

    registry.register("a1", old)
    registry.register("a1", new)  # same id reconnects; displaces `old`

    # `new` owns the id; `old` was closed so its callers unblock and it can't route.
    assert registry.pick("a1") is new
    with pytest.raises(WorkbenchUnavailableError, match="agent connection closed"):
        next(old.request(IsRunningRequest(container_name="x")))

    # The stale `old` socket tearing down must NOT evict its live successor.
    registry.unregister("a1", old)
    assert registry.pick("a1") is new

    # The current owner tearing down does remove it.
    registry.unregister("a1", new)
    assert registry.list_agents() == []

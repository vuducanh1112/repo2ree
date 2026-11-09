"""A daemon nested on a machine resolves names through the host's DNS servers."""

import pytest

from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName
from repo2ree_testbed.stack.machine_dns import nameservers


@pytest.mark.parametrize(
    ("resolv_conf", "expected"),
    [
        ("nameserver 10.168.68.254\n", ("10.168.68.254",)),
        ("# comment\nsearch lan\nnameserver 10.0.0.1\nnameserver 10.0.0.2\n", ("10.0.0.1", "10.0.0.2")),
        ("nameserver 127.0.0.11\noptions ndots:0\n", ()),
        ("nameserver 127.0.0.53\nnameserver 10.0.0.1\n", ("10.0.0.1",)),
        ("nameserver 8.8.8.8\nnameserver 8.8.4.4\n", ()),
        ("nameserver 8.8.8.8\nnameserver 10.0.0.1\n", ("8.8.8.8", "10.0.0.1")),
        ("nameserver fe80::1%eth0\n", ("fe80::1%eth0",)),
        ("nameserver not-an-address\nnameserver\n", ()),
        ("", ()),
    ],
)
def test_the_servers_a_nested_daemon_is_given(resolv_conf: str, expected: tuple[str, ...]) -> None:
    assert nameservers(resolv_conf) == expected


def test_only_a_machine_with_a_daemon_of_its_own_nests_one() -> None:
    assert {name for name, machine in ENVIRONMENTS.items() if machine.nested_daemon} == {EnvironmentName.DOCKER}

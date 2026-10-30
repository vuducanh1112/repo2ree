import io
import json
import tarfile

import pytest

from repo2ree_provider_docker import bench_dns


def test_the_setting_is_auto_off_or_addresses() -> None:
    assert bench_dns.parse_setting("auto") is None
    assert bench_dns.parse_setting("") is None
    assert bench_dns.parse_setting("OFF") == ()
    assert bench_dns.parse_setting("10.168.68.254, 2001:db8::1") == ("10.168.68.254", "2001:db8::1")
    with pytest.raises(ValueError, match="not an IP address"):
        bench_dns.parse_setting("dns.example.org")


def test_loopback_nameservers_are_not_resolvers_a_nested_daemon_can_use() -> None:
    resolv = (
        "# generated\nnameserver 127.0.0.11\nnameserver 10.168.68.254\nnameserver ::1\nsearch lan\noptions ndots:0\n"
    )
    assert bench_dns.nameservers(resolv) == ("10.168.68.254",)


def test_dockers_own_fallback_is_not_a_discovery() -> None:
    fallback = "nameserver 8.8.8.8\nnameserver 8.8.4.4\nnameserver 2001:4860:4860::8888\n"
    assert bench_dns.discovered(fallback) == ()
    assert bench_dns.discovered("nameserver 8.8.8.8\nnameserver 10.0.0.53\n") == ("8.8.8.8", "10.0.0.53")


def test_the_image_s_own_daemon_settings_survive_the_merge() -> None:
    existing = json.dumps({"dns": ["1.1.1.1"], "registry-mirrors": ["http://mirror:5000"]}).encode()

    merged = json.loads(bench_dns.merged_daemon_json(existing, ("10.0.0.53",)))

    assert merged == {"dns": ["10.0.0.53"], "registry-mirrors": ["http://mirror:5000"]}
    assert json.loads(bench_dns.merged_daemon_json(None, ("10.0.0.53",))) == {"dns": ["10.0.0.53"]}
    assert json.loads(bench_dns.merged_daemon_json(b"not json", ("10.0.0.53",))) == {"dns": ["10.0.0.53"]}


def test_the_archive_unpacks_at_etc_into_docker_daemon_json() -> None:
    with tarfile.open(fileobj=io.BytesIO(bench_dns._daemon_json_archive(b"{}\n"))) as archive:
        names = archive.getnames()
        content = archive.extractfile("docker/daemon.json")
        assert content is not None
        assert content.read() == b"{}\n"
    assert names == ["docker", "docker/daemon.json"]

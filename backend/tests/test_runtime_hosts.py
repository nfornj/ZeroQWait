from unittest.mock import patch

from shared.runtime_hosts import resolve_runtime_host


def test_resolve_runtime_host_keeps_service_alias_inside_container():
    with patch("shared.runtime_hosts._is_container_runtime", return_value=True):
        assert resolve_runtime_host("redis") == "redis"


def test_resolve_runtime_host_falls_back_to_localhost_for_compose_aliases_outside_container():
    with (
        patch("shared.runtime_hosts._is_container_runtime", return_value=False),
        patch("shared.runtime_hosts.socket.getaddrinfo", side_effect=OSError("no host")),
    ):
        assert resolve_runtime_host("redis") == "localhost"
        assert resolve_runtime_host("db") == "localhost"


def test_resolve_runtime_host_leaves_non_compose_hosts_unchanged_when_unresolvable():
    with (
        patch("shared.runtime_hosts._is_container_runtime", return_value=False),
        patch("shared.runtime_hosts.socket.getaddrinfo", side_effect=OSError("no host")),
    ):
        assert resolve_runtime_host("redis.zeroqwait.svc.cluster.local") == "redis.zeroqwait.svc.cluster.local"
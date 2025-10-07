from __future__ import annotations

import pytest

from codex_plus import port_guard
from codex_plus.port_guard import PortState, PortCheckResult


@pytest.fixture()
def reset_module_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(port_guard, "_LSOF_COMMAND", ["lsof"])
    monkeypatch.setattr(port_guard, "_DEFAULT_EXPECTED_MARKERS", tuple(port_guard._DEFAULT_EXPECTED_MARKERS))


def test_check_port_ownership_free_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(port_guard, "_run_lsof", lambda _port: [])
    result = port_guard.check_port_ownership(port=10000, expected_markers=("codex_plus",))
    assert result == PortCheckResult(state=PortState.FREE, processes=())


def test_check_port_ownership_owned_by_proxy_via_command(monkeypatch: pytest.MonkeyPatch) -> None:
    processes = [
        port_guard.ProcessInfo(pid=1234, command="python -c from codex_plus.main_sync_cffi import app"),
    ]
    monkeypatch.setattr(port_guard, "_run_lsof", lambda _port: processes)
    result = port_guard.check_port_ownership(port=10000, expected_markers=("codex_plus",))
    assert result.state is PortState.OWNED_BY_PROXY
    assert result.processes == tuple(processes)


def test_check_port_ownership_owned_by_proxy_via_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(port_guard, "_run_lsof", lambda _port: [port_guard.ProcessInfo(pid=4321, command="python other")])

    def fake_health(url: str, timeout: float) -> bool:
        assert url == "http://127.0.0.1:10000/health"
        assert timeout == 1.0
        return True

    monkeypatch.setattr(port_guard, "_probe_health", fake_health)
    result = port_guard.check_port_ownership(
        port=10000,
        expected_markers=("codex_plus",),
        health_url="http://127.0.0.1:10000/health",
    )
    assert result.state is PortState.OWNED_BY_PROXY


def test_check_port_ownership_occupied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(port_guard, "_run_lsof", lambda _port: [port_guard.ProcessInfo(pid=77, command="redis-server")])
    monkeypatch.setattr(port_guard, "_probe_health", lambda _url, _timeout: False)
    result = port_guard.check_port_ownership(port=10000, expected_markers=("codex_plus",))
    assert result.state is PortState.OCCUPIED_OTHER
    assert result.processes[0].pid == 77


def test_check_port_ownership_unknown_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = port_guard.PortGuardError("lsof missing")

    def raising_lsof(_port: int) -> tuple[port_guard.ProcessInfo, ...]:
        raise error

    monkeypatch.setattr(port_guard, "_run_lsof", raising_lsof)
    result = port_guard.check_port_ownership(port=10000, expected_markers=("codex_plus",))
    assert result.state is PortState.UNKNOWN

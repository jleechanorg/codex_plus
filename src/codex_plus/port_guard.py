from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


_DEFAULT_EXPECTED_MARKERS: Sequence[str] = (
    "codex_plus",
    "main_sync_cffi",
    "uvicorn",
)
_LSOF_COMMAND: Sequence[str] = ("lsof", "-nP")


class PortGuardError(RuntimeError):
    """Raised when inspecting the system state fails."""


class PortState(str, Enum):
    FREE = "free"
    OWNED_BY_PROXY = "owned_by_proxy"
    OCCUPIED_OTHER = "occupied_other"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    command: str


@dataclass(frozen=True)
class PortCheckResult:
    state: PortState
    processes: tuple[ProcessInfo, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "processes": [
                {"pid": p.pid, "command": p.command}
                for p in self.processes
            ],
        }


def _run_lsof(port: int) -> list[ProcessInfo]:
    command = list(_LSOF_COMMAND) + [f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"]
    try:
        proc = subprocess.run(  # noqa: S603 - controlled command, arguments list
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on environment
        raise PortGuardError("lsof command not available") from exc
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - defensive
        raise PortGuardError("lsof command timed out") from exc

    stdout = proc.stdout or ""
    if not stdout.strip():
        return []

    processes: list[ProcessInfo] = []
    current_pid: int | None = None
    current_command: str | None = None

    for raw_line in stdout.splitlines():
        if not raw_line:
            continue
        tag, value = raw_line[0], raw_line[1:]
        if tag == "p":
            if current_pid is not None and current_command is not None:
                processes.append(ProcessInfo(pid=current_pid, command=current_command))
            try:
                current_pid = int(value)
            except ValueError:
                current_pid = None
            current_command = None
        elif tag == "c":
            current_command = value

    if current_pid is not None and current_command is not None:
        processes.append(ProcessInfo(pid=current_pid, command=current_command))

    return processes


def _probe_health(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - intentional
            if response.status >= 200 and response.status < 300:
                return True
    except (urllib.error.URLError, ValueError, TimeoutError):
        return False
    return False


def _matches_expected(process: ProcessInfo, expected_markers: Iterable[str]) -> bool:
    haystack = process.command.lower()
    return any(marker.lower() in haystack for marker in expected_markers)


def check_port_ownership(
    port: int,
    *,
    expected_markers: Sequence[str] | None = None,
    health_url: str | None = None,
    health_timeout: float = 1.0,
) -> PortCheckResult:
    markers = expected_markers or _DEFAULT_EXPECTED_MARKERS
    try:
        processes = tuple(_run_lsof(port))
    except PortGuardError as exc:
        logger.debug("port guard failed", exc_info=exc)
        return PortCheckResult(state=PortState.UNKNOWN, processes=())

    if not processes:
        return PortCheckResult(state=PortState.FREE, processes=())

    for process in processes:
        if _matches_expected(process, markers):
            return PortCheckResult(state=PortState.OWNED_BY_PROXY, processes=processes)

    if health_url and _probe_health(health_url, timeout=health_timeout):
        return PortCheckResult(state=PortState.OWNED_BY_PROXY, processes=processes)

    return PortCheckResult(state=PortState.OCCUPIED_OTHER, processes=processes)


_EXIT_CODE_BY_STATE = {
    PortState.OWNED_BY_PROXY: 0,
    PortState.FREE: 10,
    PortState.OCCUPIED_OTHER: 20,
    PortState.UNKNOWN: 30,
}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Inspect ownership of the Codex proxy port")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--expect", action="append", dest="expected", default=[])
    parser.add_argument("--health-url", dest="health_url")
    parser.add_argument("--health-timeout", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    expected = tuple(args.expected) if args.expected else None
    result = check_port_ownership(
        port=args.port,
        expected_markers=expected,
        health_url=args.health_url,
        health_timeout=args.health_timeout,
    )

    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        summary = result.to_dict()
        printable = json.dumps(summary, indent=2)
        print(printable)

    return _EXIT_CODE_BY_STATE[result.state]


def main() -> None:  # pragma: no cover - simple wrapper
    sys.exit(_cli())


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

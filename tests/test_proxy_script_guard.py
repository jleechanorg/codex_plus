from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "proxy.sh"


@pytest.mark.skipif(not SCRIPT_PATH.exists(), reason="proxy script missing")
def test_proxy_enable_exits_when_guard_reports_owned(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    env = os.environ.copy()
    env.update(
        {
            "CODEX_PROXY_GUARD_STATE": "owned_by_proxy",
            "CODEX_PROXY_RUNTIME_DIR": str(runtime_dir),
        }
    )

    result = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT_PATH), "enable"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Proxy already running" in result.stdout
    assert not (runtime_dir / "proxy.pid").exists()

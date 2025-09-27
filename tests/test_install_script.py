"""Tests for the install.sh helper script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKER = "# >>> codex-plus setup >>>"


def run_install(tmp_path: Path, shell: str = "/bin/bash") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(tmp_path),
        "SHELL": shell,
    })
    return subprocess.run(
        ["bash", str(REPO_ROOT / "install.sh")],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_install_appends_snippet_once(tmp_path: Path) -> None:
    rc_path = tmp_path / ".bashrc"
    rc_path.write_text("# existing rc\n")

    first_run = run_install(tmp_path)
    content = rc_path.read_text()

    assert f"Using shell configuration: {rc_path}" in first_run.stdout
    assert MARKER in content
    assert content.count(MARKER) == 1
    assert 'alias codex-plus-proxy=\'codex_plus_proxy\'' in content
    assert 'alias codexd=' in content
    assert f'export CODEX_PLUS_REPO="{REPO_ROOT.resolve()}"' in content
    assert 'export CODEX_PLUS_PROXY_PORT="10000"' in content

    initial_content = content

    second_run = run_install(tmp_path)
    assert "Codex-Plus snippet already present" in second_run.stdout
    assert rc_path.read_text() == initial_content

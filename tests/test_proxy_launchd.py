from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import pytest
import shlex
import shutil


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "proxy.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


@pytest.mark.skipif(not SCRIPT_PATH.exists(), reason="proxy script missing")
def test_proxy_enable_on_darwin_installs_launchd(tmp_path: Path) -> None:
    repo_root = SCRIPT_PATH.parent
    venv_path = repo_root / "venv"
    created_venv = False
    if not venv_path.exists():
        (venv_path / "bin").mkdir(parents=True)
        (venv_path / "bin" / "activate").write_text("#!/bin/bash\n")
        created_venv = True

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_home = tmp_path / "home"
    (fake_home / "Library" / "LaunchAgents").mkdir(parents=True)

    launchctl_calls = runtime_dir / "launchctl_calls.log"

    _write_executable(
        fake_bin / "uname",
        "#!/bin/bash\n"
        "if [ \"${1:-}\" = \"-s\" ]; then\n"
        "  echo Darwin\n"
        "else\n"
        "  echo Darwin\n"
        "fi\n",
    )

    _write_executable(
        fake_bin / "curl",
        "#!/bin/bash\n"
        "exit 0\n",
    )

    system_ps = shlex.quote(shutil.which("ps") or "/bin/ps")

    _write_executable(
        fake_bin / "ps",
        "#!/bin/bash\n"
        "if [ \"${1:-}\" = \"-p\" ]; then\n"
        "  shift\n"
        "  pid=$1\n"
        "  shift\n"
        "  if [ \"${1:-}\" = \"-o\" ] && [ \"${2:-}\" = \"command=\" ]; then\n"
        "    echo python main_sync_cffi\n"
        "    exit 0\n"
        "  fi\n"
        "fi\n"
        f"exec {system_ps} \"$@\"\n",
    )

    _write_executable(
        fake_bin / "launchctl",
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f"echo \"$@\" >> {launchctl_calls}\n"
        "runtime=\"${CODEX_PROXY_RUNTIME_DIR:-}\"\n"
        "case \"${1:-}\" in\n"
        "  start)\n"
        "    proxy_script=\"${runtime}/main_sync_cffi_fake.sh\"\n"
        "    if [ ! -f \"${proxy_script}\" ]; then\n"
        "      cat <<'EOS' > \"${proxy_script}\"\n"
        "#!/bin/bash\n"
        "trap 'exit 0' TERM INT\n"
        "while true; do\n"
        "  sleep 1\n"
        "done\n"
        "EOS\n"
        "      chmod +x \"${proxy_script}\"\n"
        "    fi\n"
        "    bash \"${proxy_script}\" &\n"
        "    child=$!\n"
        "    echo \"${child}\" > \"${runtime}/proxy.pid\"\n"
        "    echo \"${child}\" > \"${runtime}/launched.pid\"\n"
        "    ;;\n"
        "  stop)\n"
        "    if [ -f \"${runtime}/launched.pid\" ]; then\n"
        "      child=$(cat \"${runtime}/launched.pid\")\n"
        "      kill -TERM \"${child}\" >/dev/null 2>&1 || true\n"
        "      rm -f \"${runtime}/launched.pid\"\n"
        "    fi\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "CODEX_PROXY_RUNTIME_DIR": str(runtime_dir),
            "HOME": str(fake_home),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    env.pop("CODEX_PROXY_GUARD_STATE", None)

    result = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT_PATH), "enable"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    try:
        assert result.returncode == 0, result.stderr
        assert "LaunchAgent installed" in result.stdout
        assert "Proxy started successfully under launchd" in result.stdout

        launch_agent_path = fake_home / "Library" / "LaunchAgents" / "com.codex.plus.proxy.plist"
        assert launch_agent_path.exists()

        launchd_env = runtime_dir / "launchd.env"
        assert launchd_env.exists()
        assert "CODEX_PLUS_PROVIDER_MODE=openai" in launchd_env.read_text()

        error_log = runtime_dir / "proxy.err"
        stdout_log = runtime_dir / "proxy.log"
        launchd_stdout = runtime_dir / "launchd.out"
        launchd_stderr = runtime_dir / "launchd.err"
        for path in (error_log, stdout_log, launchd_stdout, launchd_stderr):
            assert path.exists()

        assert launchctl_calls.exists()
        launchctl_output = launchctl_calls.read_text()
        assert "load" in launchctl_output
        assert "start" in launchctl_output
    finally:
        pid_file = runtime_dir / "proxy.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except ValueError:
                pid = None
            if pid:
                os.kill(pid, signal.SIGTERM)
        subprocess.run(  # noqa: S603
            ["bash", str(SCRIPT_PATH), "disable"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if created_venv:
            shutil.rmtree(venv_path)


@pytest.mark.skipif(not SCRIPT_PATH.exists(), reason="proxy script missing")
def test_proxy_help_lists_commands() -> None:
    result = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for command in ("enable", "disable", "start", "stop", "status", "restart", "autostart", "help"):
        assert command in result.stdout

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

import pytest
import requests

REQUIRED_ENV_VARS = [
    "CEREBRAS_API_KEY",
    "CEREBRAS_BASE_URL",
    "CEREBRAS_MODEL",
]


def pytest_configure(config):  # noqa: D401 ANN001
    """Register custom marks used by the Cerebras integration suite."""
    config.addinivalue_line(
        "markers",
        "cerebras: marks Cerebras end-to-end integration tests",
    )


def _load_env_from_shell(var_names: Iterable[str]) -> None:
    """Attempt to populate missing env vars by sourcing the user's shell config."""
    keys = list(var_names)
    if not keys:
        return

    python_block = "\n".join(
        [
            "import os",
            f"keys = {keys!r}",
            "for key in keys:",
            "    value = os.environ.get(key, '')",
            "    print(f'{key}={value}')",
        ]
    )

    script = "source ~/.bashrc >/dev/null 2>&1\npython - <<'PY'\n" + python_block + "\nPY\n"
    try:
        output = subprocess.check_output(  # noqa: S603,S607
            ["bash", "-ic", script],
            text=True,
            env=os.environ,
            stdin=None,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return

    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value:
            os.environ.setdefault(key, value)



def _ensure_prerequisites() -> None:
    if os.getenv("NO_NETWORK") == "1":
        pytest.skip("Cerebras integration tests require network access")

    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        _load_env_from_shell(missing)
        missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        pytest.skip(
            f"Skipping Cerebras integration tests; missing environment variables: {', '.join(missing)}"
        )

    if not shutil.which("codex"):
        pytest.skip("Codex CLI is not installed on PATH")


def _wait_for_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - best-effort health check
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url} to become healthy; last error: {last_error}")


@pytest.fixture(scope="session")
def chatgpt_proxy() -> None:
    """Ensure the default ChatGPT proxy on port 10000 is running."""
    _ensure_prerequisites()
    subprocess.run(["./proxy.sh", "restart"], check=True)
    try:
        _wait_for_health("http://127.0.0.1:10000/health", timeout=45)
    except Exception:
        subprocess.run(["./proxy.sh", "disable"], check=False)
        raise
    yield
    subprocess.run(["./proxy.sh", "disable"], check=False)


@pytest.fixture(scope="session")
def cerebras_proxy(chatgpt_proxy):  # noqa: ANN001
    """Launch the Cerebras proxy on port 10001 for the duration of the test session."""
    env: Dict[str, str] = dict(os.environ)
    env.setdefault("CODEX_PLUS_UPSTREAM_URL", env["CEREBRAS_BASE_URL"])
    env.setdefault("CODEX_PLUS_PROVIDER_MODE", "cerebras")
    env.setdefault("OPENAI_API_KEY", env["CEREBRAS_API_KEY"])
    env.setdefault("OPENAI_BASE_URL", env["CEREBRAS_BASE_URL"])
    env.setdefault("OPENAI_MODEL", env["CEREBRAS_MODEL"])

    log_path = Path("/tmp/codex_plus/proxy_10001_test.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")

    proc = subprocess.Popen(  # noqa: S603 - intentional command execution
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.codex_plus.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "10001",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )

    try:
        _wait_for_health("http://127.0.0.1:10001/health", timeout=60)
    except Exception:
        proc.terminate()
        proc.wait(timeout=5)
        log_file.close()
        raise

    yield

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    log_file.close()


@pytest.fixture(scope="session")
def codex_env(cerebras_proxy):  # noqa: ANN001
    env = dict(os.environ)
    env["OPENAI_BASE_URL"] = "http://localhost:10001"
    env.setdefault("NO_COLOR", "1")
    return env

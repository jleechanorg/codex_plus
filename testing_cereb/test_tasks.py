"""End-to-end integration tests exercising the Cerebras proxy via Codex CLI."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.cerebras


def _run_codex(prompt: str, env: dict[str, str], timeout: int = 240) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603 - intentional command execution
        ["codex", "exec", "--yolo", prompt],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(
            "\n".join(
                [
                    "Codex command failed",
                    f"exit code: {result.returncode}",
                    "STDOUT:",
                    result.stdout.strip(),
                    "STDERR:",
                    result.stderr.strip(),
                ]
            )
        )
    return result


@pytest.mark.parametrize(
    "description,extension,prompt,validator",
    [
        (
            "small_script",
            ".py",
            "Using the shell tool, write {path} containing a Python function bubble_sort(items) that returns a sorted list plus a __main__ guard demonstrating it",
            lambda content: "def bubble_sort" in content and "if __name__ ==" in content,
        ),
        (
            "medium_cli",
            ".py",
            "Use the shell tool to run a single bash command of the form cat <<'EOF' > {path} ... EOF that writes a Python CLI which reads JSON from stdin, sorts the numbers with bubble_sort, and prints JSON output",
            lambda content: ("json.load" in content or "json.loads" in content) and "bubble_sort" in content,
        ),
        (
            "large_report",
            ".md",
            "Using the shell tool, write {path} with a detailed markdown report explaining bubble sort, including sections for algorithm steps, complexity tables, and a Python example",
            lambda content: "#" in content and "Complexity" in content and "```python" in content,
        ),
    ],
)
@pytest.mark.timeout(420)
def test_cerebras_codex_tasks(description: str, extension: str, prompt: str, validator, codex_env):  # noqa: ANN001
    suffix = uuid.uuid4().hex
    last_result: subprocess.CompletedProcess[str] | None = None
    target: Path | None = None

    for attempt in range(5):
        target = Path(f"/tmp/cereb_{description}_{suffix}_{attempt}{extension}")
        if target.exists():
            target.unlink()

        formatted_prompt = prompt.format(path=str(target))
        try:
            last_result = _run_codex(formatted_prompt, env=codex_env)
        except subprocess.TimeoutExpired:
            last_result = None
            continue
        if target.exists():
            break
    else:
        if last_result is None:
            pytest.fail(
                "Codex command timed out for all attempts",
                pytrace=False,
            )
        debug_message = "\n".join(
            [
                f"Expected output file {target} to be created",
                "STDOUT:",
                last_result.stdout.strip(),
                "STDERR:",
                last_result.stderr.strip(),
            ]
        )
        pytest.fail(debug_message)

    assert target is not None
    content = target.read_text(encoding="utf-8")
    assert validator(content), f"Generated content did not match expectations for {description}"
    assert len(content) > 50

    if last_result is not None and last_result.returncode != 0:
        assert "MCP client" in last_result.stderr


def test_codex_cereb_wrapper_exec(codex_env):  # noqa: ANN001
    """Ensure the convenience wrapper launches both proxies and executes a task."""
    base_suffix = uuid.uuid4().hex
    prompt_template = (
        "Using the shell tool, write {path} containing a Python function bubble_sort(items) "
        "that returns a sorted list plus a __main__ guard demonstrating it"
    )

    last_result: subprocess.CompletedProcess[str] | None = None

    for attempt in range(5):
        target = Path(f"/tmp/cereb_wrapper_{base_suffix}_{attempt}.py")
        if target.exists():
            target.unlink()

        formatted_prompt = prompt_template.format(path=str(target))
        result = subprocess.run(  # noqa: S603 - intentional command execution
            ["./codex_cereb.sh", "exec", "--yolo", formatted_prompt],
            cwd=Path(__file__).resolve().parents[1],
            env=codex_env,
            text=True,
            capture_output=True,
            timeout=360,
            check=False,
        )
        last_result = result

        if target.exists():
            content = target.read_text(encoding="utf-8")
            assert "def bubble_sort" in content and "if __name__ ==" in content
            if result.returncode != 0:
                assert "MCP client" in result.stderr
            break
    else:
        assert last_result is not None
        pytest.fail(
            "\n".join(
                [
                    "codex_cereb.sh did not produce the expected file after 5 attempts",
                    "STDOUT:",
                    last_result.stdout.strip(),
                    "STDERR:",
                    last_result.stderr.strip(),
                ]
            ),
            pytrace=False,
        )

    content = target.read_text(encoding="utf-8")
    assert "def bubble_sort" in content and "if __name__ ==" in content

    if last_result is not None and last_result.returncode != 0:
        assert "MCP client" in last_result.stderr

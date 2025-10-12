from pathlib import Path
import sys

# Ensure scripts directory is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_commands import sync_commands


def test_sync_commands_copies_reviewdeep(tmp_path):
    source_dir = REPO_ROOT / ".codexplus" / "commands"
    destination = tmp_path / ".claude" / "commands"

    updated = sync_commands(source_dir, [destination])

    reviewdeep_path = destination / "reviewdeep.md"
    assert reviewdeep_path.exists()
    assert reviewdeep_path.read_text(encoding="utf-8") == (
        source_dir / "reviewdeep.md"
    ).read_text(encoding="utf-8")
    assert reviewdeep_path in updated

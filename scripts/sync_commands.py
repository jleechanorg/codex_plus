"""Utility to sync slash command definitions into user command directories."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, List


def sync_commands(source_dir: Path, destinations: Iterable[Path]) -> List[Path]:
    """Copy markdown command files from ``source_dir`` into ``destinations``.

    The directory structure beneath ``source_dir`` is preserved for each
    destination. Files are copied when they are missing or when the contents
    differ from the source version. Returns a list of destination files that
    were created or updated.
    """

    if not source_dir.exists():
        raise FileNotFoundError(f"Command source directory not found: {source_dir}")

    updated: List[Path] = []
    source_dir = source_dir.resolve()
    command_files = sorted(p for p in source_dir.rglob("*.md") if p.is_file())

    for source_file in command_files:
        relative_path = source_file.relative_to(source_dir)
        content = source_file.read_bytes()
        for destination_root in destinations:
            destination_root.mkdir(parents=True, exist_ok=True)
            destination_file = (destination_root / relative_path).resolve()
            destination_file.parent.mkdir(parents=True, exist_ok=True)

            if not destination_file.exists() or destination_file.read_bytes() != content:
                shutil.copy2(source_file, destination_file)
                updated.append(destination_file)

    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync slash command markdown files")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".codexplus" / "commands",
        help="Directory containing canonical command definitions.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        action="append",
        dest="destinations",
        help="Destination directory for synced commands (may be specified multiple times).",
    )
    parser.add_argument(
        "--include-defaults",
        action="store_true",
        help="Include default destinations (~/.codexplus/commands and ~/.claude/commands).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file logging and only show a summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    destinations: List[Path] = []
    if args.destinations:
        destinations.extend(args.destinations)
    if args.include_defaults or not destinations:
        home = Path.home()
        destinations.extend([
            home / ".codexplus" / "commands",
            home / ".claude" / "commands",
        ])

    updated_files = sync_commands(args.source, destinations)

    if not args.quiet:
        if updated_files:
            print("Synced command files:")
            for file_path in updated_files:
                print(f" - {file_path}")
        else:
            print("Commands already up to date.")


if __name__ == "__main__":
    main()

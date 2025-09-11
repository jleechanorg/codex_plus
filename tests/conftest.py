import sys
from pathlib import Path

# Ensure project root is on sys.path for imports like `from main import app`
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (ROOT, SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

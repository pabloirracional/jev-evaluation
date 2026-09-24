"""Loads KEY=value pairs from the project's .env file into os.environ (stdlib only).

Variables already set in the shell win, so a one-off `$env:X = ...` still overrides .env.
"""
import os
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def load(path=ENV_FILE):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():   # -sig: Notepad/PowerShell add a BOM
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

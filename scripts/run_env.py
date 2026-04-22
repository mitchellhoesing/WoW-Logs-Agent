"""Activate the project venv and run the wowlogs-agent CLI.

Usage:
    python scripts/run_env.py compare \
        --character-a-log '<reportA>?fight=<N>' \
        --character-b-log '<reportB>?fight=<M>' \
        --character-a <name> [--character-b <name>]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _venv_executable(venv: Path, name: str) -> Path | None:
    for candidate in (
        venv / "Scripts" / f"{name}.exe",
        venv / "Scripts" / name,
        venv / "bin" / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    venv = root / ".venv"
    if not venv.is_dir():
        sys.stderr.write(f"Virtual environment not found at {venv}\n")
        return 1

    cli = _venv_executable(venv, "wowlogs-agent")
    if cli is None:
        sys.stderr.write(
            f"wowlogs-agent entry point not found in {venv}. "
            "Run `make install` (or `pip install -e '.[dev]'`) first.\n"
        )
        return 1

    args = [str(cli), *sys.argv[1:]]
    if os.name == "nt":
        import subprocess

        return subprocess.call(args)
    os.execv(str(cli), args)
    return 0  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())

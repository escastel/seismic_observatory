"""python -m app.replay <command> (contracts/replay-cli.md)."""

from __future__ import annotations

import sys


def run() -> int:
    from .cli import main

    return main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(run())

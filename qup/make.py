"""Stable build entry point for QUP blueprint artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


TARGETS = {
    "cell": "cell.py",
    "norm": "norm.py",
    "recy": "recy.py",
    "sort": "sort.py",
    "tier": "tier.py",
    "high": "high.py",
    "qup": "qup.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).parent
    subprocess.run(
        [
            sys.executable,
            str(root / TARGETS[args.target]),
            "--output",
            str(root / f"{args.target}.txt"),
            "--json",
            str(root / f"{args.target}.json"),
        ],
        check=True,
    )
    if not args.skip_tests:
        subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"],
            check=True,
            cwd=root,
        )


if __name__ == "__main__":
    main()

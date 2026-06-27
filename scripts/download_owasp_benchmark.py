#!/usr/bin/env python3
"""Obtain OWASP BenchmarkJava and stage the organizer-only answer key.

What this script does:

1. ``git clone`` https://github.com/OWASP-Benchmark/BenchmarkJava.git into
   ``third_party/BenchmarkJava`` -- only if that directory does not already
   exist. If it already exists, the clone is skipped and only an existence
   check is performed.
2. Copy ``expectedresults-1.2.csv`` into ``organizer/expected/``.
3. Confirm the Java testcases directory is present and report the count.
4. ``third_party/`` is listed in ``.gitignore`` so the external repository is
   never committed into this repository.

If the network clone fails, manual clone instructions are printed.

Usage::

    python scripts/download_owasp_benchmark.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from benchmark_common import (
    BENCHMARK_CLONE_DIR,
    BENCHMARK_GIT_URL,
    EXPECTED_CSV,
    EXPECTED_DIR,
    TESTCASE_DIR,
    THIRD_PARTY_DIR,
)

CLONE_COMMAND: list[str] = [
    "git",
    "clone",
    BENCHMARK_GIT_URL,
    str(BENCHMARK_CLONE_DIR),
]


def _manual_instructions() -> str:
    return (
        "Could not clone OWASP BenchmarkJava automatically.\n"
        "Please clone it manually from the repository root:\n\n"
        f"    {' '.join(CLONE_COMMAND)}\n\n"
        "Then re-run:\n\n"
        "    python scripts/download_owasp_benchmark.py\n"
    )


def clone_if_needed() -> bool:
    """Clone the benchmark unless it already exists.

    Returns ``True`` if the clone directory is usable afterwards.
    """
    if BENCHMARK_CLONE_DIR.exists():
        print(f"[skip] {BENCHMARK_CLONE_DIR} already exists -- not re-cloning.")
        return True

    THIRD_PARTY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[clone] {' '.join(CLONE_COMMAND)}")
    try:
        subprocess.run(CLONE_COMMAND, check=True)
    except FileNotFoundError:
        print("[error] 'git' executable not found on PATH.", file=sys.stderr)
        print(_manual_instructions(), file=sys.stderr)
        return False
    except subprocess.CalledProcessError as exc:
        print(f"[error] git clone failed (exit code {exc.returncode}).", file=sys.stderr)
        # Clean up a partial clone so a re-run starts fresh.
        if BENCHMARK_CLONE_DIR.exists():
            shutil.rmtree(BENCHMARK_CLONE_DIR, ignore_errors=True)
        print(_manual_instructions(), file=sys.stderr)
        return False
    return True


def copy_expected_results() -> bool:
    """Copy ``expectedresults-1.2.csv`` into ``organizer/expected/``."""
    source = BENCHMARK_CLONE_DIR / "expectedresults-1.2.csv"
    if not source.is_file():
        print(f"[error] expected results not found at {source}", file=sys.stderr)
        return False
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, EXPECTED_CSV)
    print(f"[ok] copied answer key -> {EXPECTED_CSV}")
    return True


def check_testcases() -> bool:
    """Verify the Java testcases directory exists and report how many cases."""
    if not TESTCASE_DIR.is_dir():
        print(f"[error] testcases directory missing: {TESTCASE_DIR}", file=sys.stderr)
        return False
    java_files = sorted(TESTCASE_DIR.glob("BenchmarkTest*.java"))
    print(f"[ok] testcases directory: {TESTCASE_DIR}")
    print(f"[ok] found {len(java_files)} BenchmarkTest*.java files")
    return len(java_files) > 0


def main() -> int:
    if not clone_if_needed():
        return 1
    ok = copy_expected_results()
    ok = check_testcases() and ok
    if not ok:
        return 1
    print("\nDone. The answer key is in organizer/expected/ (organizer-only).")
    print("Next: python scripts/select_cases.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

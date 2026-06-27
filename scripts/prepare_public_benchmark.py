#!/usr/bin/env python3
"""Build the participant-facing public benchmark from the selected cases.

Reads ``organizer/selected_cases.csv`` and copies ONLY the corresponding Java
testcase files into ``benchmark/public/cases/``. It also (re)generates the
report template participants must fill in.

To avoid leaking answers, the following are deliberately NEVER copied into the
public folder:

* ``expectedresults-1.2.csv`` (the answer key)
* anything under ``organizer/``
* OWASP Benchmark scorecards / official scoring output
* any file that reveals the ground-truth label

The result is a self-contained, label-free folder safe to hand to participants::

    benchmark/public/
    +-- cases/
    |   +-- BenchmarkTest00001.java
    |   +-- ...
    +-- report_template.json
    +-- README.md

Usage::

    python scripts/prepare_public_benchmark.py
"""

from __future__ import annotations

import csv
import json
import shutil
import sys

from benchmark_common import (
    PUBLIC_CASES_DIR,
    REPORT_TEMPLATE,
    SELECTED_CASES_CSV,
    TESTCASE_DIR,
)

# The canonical report schema handed to participants (one JSON per case).
REPORT_TEMPLATE_CONTENT: dict[str, object] = {
    "test_name": "",
    "model_or_agent": "",
    "model_name": "",
    "web_search_used": False,
    "is_vulnerable": None,
    "bug_type": "",
    "cwe": "",
    "vulnerable_file": "",
    "vulnerable_function": "",
    "root_cause": "",
    "security_impact": "",
    "patch_strategy": "",
    "confidence": 0.0,
}


def read_selected_test_names() -> list[str]:
    """Read the list of selected test names from ``selected_cases.csv``."""
    if not SELECTED_CASES_CSV.is_file():
        raise FileNotFoundError(
            f"{SELECTED_CASES_CSV} not found. Run scripts/select_cases.py first."
        )
    names: list[str] = []
    with SELECTED_CASES_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "test_name" not in reader.fieldnames:
            raise ValueError(f"{SELECTED_CASES_CSV} is missing a 'test_name' column.")
        for row in reader:
            name = (row.get("test_name") or "").strip()
            if name:
                names.append(name)
    if not names:
        raise ValueError(f"No test names found in {SELECTED_CASES_CSV}.")
    return names


def reset_public_cases() -> None:
    """Clear and recreate ``benchmark/public/cases/`` so stale files never leak."""
    if PUBLIC_CASES_DIR.exists():
        shutil.rmtree(PUBLIC_CASES_DIR)
    PUBLIC_CASES_DIR.mkdir(parents=True, exist_ok=True)


def copy_cases(test_names: list[str]) -> tuple[int, list[str]]:
    """Copy each selected Java file into the public folder.

    Returns ``(copied_count, missing_names)``.
    """
    if not TESTCASE_DIR.is_dir():
        raise FileNotFoundError(
            f"Testcases directory missing: {TESTCASE_DIR}\n"
            "Run scripts/download_owasp_benchmark.py first."
        )
    copied = 0
    missing: list[str] = []
    for name in test_names:
        source = TESTCASE_DIR / f"{name}.java"
        if not source.is_file():
            missing.append(name)
            continue
        shutil.copy2(source, PUBLIC_CASES_DIR / f"{name}.java")
        copied += 1
    return copied, missing


def write_report_template() -> None:
    REPORT_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_TEMPLATE.open("w", encoding="utf-8") as fh:
        json.dump(REPORT_TEMPLATE_CONTENT, fh, indent=2)
        fh.write("\n")


def write_public_readme(test_names: list[str]) -> None:
    lines = [
        "# Public Benchmark (participant-facing)",
        "",
        "This folder contains everything a participant needs and nothing that",
        "reveals the answers.",
        "",
        "## Contents",
        "",
        "- `cases/` — Java testcases to audit (one `BenchmarkTestNNNNN.java` each).",
        "- `report_template.json` — the JSON schema to copy per case.",
        "",
        "## Your task",
        "",
        "For each Java file in `cases/`, read the code and decide whether it",
        "contains a real vulnerability. Produce **one JSON file per case** named",
        "after the test (e.g. `BenchmarkTest00001.json`), following",
        "`report_template.json`.",
        "",
        "No flag capture and no exploit are required — this is a static",
        "code-audit task. See `docs/participant-guide.md` for full rules.",
        "",
        f"## Cases in this round ({len(test_names)})",
        "",
    ]
    lines += [f"- {name}" for name in test_names]
    lines.append("")
    (PUBLIC_CASES_DIR.parent / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    try:
        test_names = read_selected_test_names()
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    try:
        reset_public_cases()
        copied, missing = copy_cases(test_names)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    write_report_template()
    write_public_readme(test_names)

    print(f"[ok] copied {copied}/{len(test_names)} Java cases -> {PUBLIC_CASES_DIR}")
    if missing:
        print(f"[warn] {len(missing)} case(s) not found in benchmark: {', '.join(missing)}",
              file=sys.stderr)
    print(f"[ok] wrote {REPORT_TEMPLATE}")
    print(f"[ok] wrote {PUBLIC_CASES_DIR.parent / 'README.md'}")
    print("\nThe public folder is safe to distribute (no answer labels included).")
    return 0 if copied > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

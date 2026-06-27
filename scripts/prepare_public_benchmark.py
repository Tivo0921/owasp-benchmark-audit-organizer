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

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

from benchmark_common import (
    BENCHMARK_PROPERTIES,
    HELPERS_DIR,
    PUBLIC_DIR,
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


def read_selected_test_names(selected_csv: Path) -> list[str]:
    """Read the list of selected test names from a ``selected_cases.csv``."""
    if not selected_csv.is_file():
        raise FileNotFoundError(
            f"{selected_csv} not found. Run scripts/select_cases.py first."
        )
    names: list[str] = []
    with selected_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "test_name" not in reader.fieldnames:
            raise ValueError(f"{selected_csv} is missing a 'test_name' column.")
        for row in reader:
            name = (row.get("test_name") or "").strip()
            if name:
                names.append(name)
    if not names:
        raise ValueError(f"No test names found in {selected_csv}.")
    return names


def reset_public_cases(cases_dir: Path) -> None:
    """Clear and recreate the public ``cases/`` folder so stale files never leak."""
    if cases_dir.exists():
        shutil.rmtree(cases_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)


def copy_cases(test_names: list[str], cases_dir: Path) -> tuple[int, list[str]]:
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
        shutil.copy2(source, cases_dir / f"{name}.java")
        copied += 1
    return copied, missing


def copy_dependencies(public_dir: Path) -> tuple[int, list[str]]:
    """Copy the shared dependencies the testcases reference.

    The testcases reference, by fully-qualified name, the
    ``org.owasp.benchmark.helpers`` package and runtime configuration in
    ``benchmark.properties``. These hold the actual data sources/sinks and the
    hash/crypto algorithm choices that determine whether a case is vulnerable,
    so an agent cannot judge correctly without them.

    Returns ``(helper_files_copied, problems)``.
    """
    problems: list[str] = []

    # 1) helpers/ package (recursively, including entities/ and filters/).
    helpers_out = public_dir / "helpers"
    if helpers_out.exists():
        shutil.rmtree(helpers_out)
    helper_count = 0
    if HELPERS_DIR.is_dir():
        shutil.copytree(HELPERS_DIR, helpers_out)
        helper_count = len(list(helpers_out.rglob("*.java")))
    else:
        problems.append(f"helpers package not found at {HELPERS_DIR}")

    # 2) benchmark.properties (hash/crypto algorithm definitions, etc.).
    if BENCHMARK_PROPERTIES.is_file():
        shutil.copy2(BENCHMARK_PROPERTIES, public_dir / "benchmark.properties")
    else:
        problems.append(f"benchmark.properties not found at {BENCHMARK_PROPERTIES}")

    return helper_count, problems


def write_report_template(template_path: Path) -> None:
    template_path.parent.mkdir(parents=True, exist_ok=True)
    with template_path.open("w", encoding="utf-8") as fh:
        json.dump(REPORT_TEMPLATE_CONTENT, fh, indent=2)
        fh.write("\n")


def write_public_readme(test_names: list[str], readme_path: Path) -> None:
    lines = [
        "# Public Benchmark (participant-facing)",
        "",
        "This folder contains everything a participant needs and nothing that",
        "reveals the answers.",
        "",
        "## Contents",
        "",
        "- `cases/` — Java testcases to audit (one `BenchmarkTestNNNNN.java` each).",
        "- `helpers/` — shared source the testcases reference by fully-qualified",
        "  name (package `org.owasp.benchmark.helpers`). **Read these** — they",
        "  define the real data sources/sinks (e.g.",
        "  `SeparateClassRequest.getTheValue()` returns a constant safe value,",
        "  while `getTheParameter()` is a genuine tainted source).",
        "- `benchmark.properties` — configuration the helpers load (e.g. which",
        "  hash/crypto algorithm is actually used). Needed to judge `hash` and",
        "  `crypto` cases correctly.",
        "- `report_template.json` — the JSON schema to copy per case.",
        "",
        "## Your task",
        "",
        "For each Java file in `cases/`, read the code (following references into",
        "`helpers/` and `benchmark.properties` as needed) and decide whether it",
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
    readme_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selected",
        type=Path,
        default=SELECTED_CASES_CSV,
        help="selection CSV to read (default: organizer/selected_cases.csv)",
    )
    parser.add_argument(
        "--public-dir",
        type=Path,
        default=PUBLIC_DIR,
        help="output public folder root (default: benchmark/public)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    public_dir: Path = args.public_dir
    cases_dir = public_dir / "cases"
    template_path = public_dir / "report_template.json"
    readme_path = public_dir / "README.md"

    try:
        test_names = read_selected_test_names(args.selected)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    try:
        reset_public_cases(cases_dir)
        copied, missing = copy_cases(test_names, cases_dir)
        helper_count, dep_problems = copy_dependencies(public_dir)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    write_report_template(template_path)
    write_public_readme(test_names, readme_path)

    print(f"[ok] copied {copied}/{len(test_names)} Java cases -> {cases_dir}")
    if missing:
        print(f"[warn] {len(missing)} case(s) not found in benchmark: {', '.join(missing)}",
              file=sys.stderr)
    print(f"[ok] copied {helper_count} helper source files -> {public_dir / 'helpers'}")
    print(f"[ok] copied benchmark.properties -> {public_dir / 'benchmark.properties'}")
    for problem in dep_problems:
        print(f"[warn] dependency missing: {problem}", file=sys.stderr)
    print(f"[ok] wrote {template_path}")
    print(f"[ok] wrote {readme_path}")
    print("\nThe public folder is safe to distribute (no answer labels included).")
    return 0 if copied > 0 and not dep_problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

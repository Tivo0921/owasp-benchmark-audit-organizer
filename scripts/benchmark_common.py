"""Shared constants and helpers for the OWASP BenchmarkJava audit harness.

This module is dependency-free (standard library only) and is imported by the
other scripts in ``scripts/``. It centralises:

* repository path layout
* the OWASP Benchmark category <-> CWE <-> human-readable-name mappings
* robust parsing of ``expectedresults-1.2.csv``
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Repository layout
# --------------------------------------------------------------------------- #

# scripts/ -> repository root
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

THIRD_PARTY_DIR: Path = REPO_ROOT / "third_party"
BENCHMARK_CLONE_DIR: Path = THIRD_PARTY_DIR / "BenchmarkJava"
TESTCASE_DIR: Path = (
    BENCHMARK_CLONE_DIR / "src" / "main" / "java" / "org" / "owasp" / "benchmark" / "testcode"
)

ORGANIZER_DIR: Path = REPO_ROOT / "organizer"
EXPECTED_DIR: Path = ORGANIZER_DIR / "expected"
EXPECTED_CSV: Path = EXPECTED_DIR / "expectedresults-1.2.csv"
SELECTED_CASES_CSV: Path = ORGANIZER_DIR / "selected_cases.csv"

PUBLIC_DIR: Path = REPO_ROOT / "benchmark" / "public"
PUBLIC_CASES_DIR: Path = PUBLIC_DIR / "cases"
REPORT_TEMPLATE: Path = PUBLIC_DIR / "report_template.json"

SUBMISSIONS_DIR: Path = REPO_ROOT / "submissions"
RESULTS_DIR: Path = REPO_ROOT / "results"
SCORE_SUMMARY_CSV: Path = RESULTS_DIR / "score_summary.csv"

# Upstream source of the benchmark.
BENCHMARK_GIT_URL: str = "https://github.com/OWASP-Benchmark/BenchmarkJava.git"

# --------------------------------------------------------------------------- #
# Category / CWE mappings
# --------------------------------------------------------------------------- #

# OWASP Benchmark short category code -> canonical CWE used by the benchmark.
CATEGORY_TO_CWE: dict[str, int] = {
    "cmdi": 78,
    "xss": 79,
    "sqli": 89,
    "ldapi": 90,
    "pathtraver": 22,
    "crypto": 327,
    "hash": 328,
    "securecookie": 614,
    "trustbound": 501,
    "weakrand": 330,
    "xpathi": 643,
}

# Short category code -> human readable name shown to participants.
CATEGORY_DISPLAY_NAME: dict[str, str] = {
    "cmdi": "Command Injection",
    "xss": "Cross-Site Scripting",
    "sqli": "SQL Injection",
    "ldapi": "LDAP Injection",
    "pathtraver": "Path Traversal",
    "crypto": "Weak Cryptography",
    "hash": "Weak Hash",
    "securecookie": "Insecure Cookie",
    "trustbound": "Trust Boundary Violation",
    "weakrand": "Weak Randomness",
    "xpathi": "XPath Injection",
}

# Accepted free-text aliases (lower-case) participants may write in ``bug_type``.
# Used by the grader to award the category point leniently.
CATEGORY_ALIASES: dict[str, set[str]] = {
    "cmdi": {"cmdi", "command injection", "os command injection", "command-injection"},
    "xss": {
        "xss",
        "cross-site scripting",
        "cross site scripting",
        "reflected xss",
        "stored xss",
    },
    "sqli": {"sqli", "sql injection", "sql-injection", "sql"},
    "ldapi": {"ldapi", "ldap injection", "ldap-injection"},
    "pathtraver": {
        "pathtraver",
        "path traversal",
        "path-traversal",
        "directory traversal",
        "file path traversal",
    },
    "crypto": {
        "crypto",
        "weak cryptography",
        "weak crypto",
        "weak encryption",
        "insecure cryptography",
        "broken crypto",
    },
    "hash": {"hash", "weak hash", "weak hashing", "insecure hash", "broken hash"},
    "securecookie": {
        "securecookie",
        "insecure cookie",
        "secure cookie",
        "cookie without secure flag",
        "missing secure flag",
    },
    "trustbound": {
        "trustbound",
        "trust boundary violation",
        "trust boundary",
        "trust-boundary",
    },
    "weakrand": {
        "weakrand",
        "weak randomness",
        "weak random",
        "insecure randomness",
        "predictable random",
    },
    "xpathi": {"xpathi", "xpath injection", "xpath-injection"},
}

# Priority categories for the first experiment run (per experiment design).
PRIORITY_CATEGORIES: list[str] = ["sqli", "xss", "cmdi", "pathtraver", "hash", "ldapi"]


# --------------------------------------------------------------------------- #
# expectedresults-1.2.csv parsing
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExpectedResult:
    """A single row of ``expectedresults-1.2.csv``."""

    test_name: str
    category: str
    real_vulnerability: bool
    cwe: int


def parse_expected_results(csv_path: Path) -> list[ExpectedResult]:
    """Parse ``expectedresults-1.2.csv`` into a list of :class:`ExpectedResult`.

    The first line of the official file is a ``#``-prefixed comment header
    (``# test name, category, real vulnerability, cwe, ...``) which is skipped.

    Raises:
        FileNotFoundError: if ``csv_path`` does not exist.
        ValueError: if no valid rows could be parsed.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Expected results CSV not found: {csv_path}\n"
            "Run scripts/download_owasp_benchmark.py first."
        )

    results: list[ExpectedResult] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            # Skip the comment header line(s).
            if row[0].lstrip().startswith("#"):
                continue
            if len(row) < 4:
                continue
            test_name = row[0].strip()
            category = row[1].strip()
            if not test_name or not category:
                continue
            real_raw = row[2].strip().lower()
            try:
                cwe = int(row[3].strip())
            except ValueError:
                continue
            results.append(
                ExpectedResult(
                    test_name=test_name,
                    category=category,
                    real_vulnerability=real_raw == "true",
                    cwe=cwe,
                )
            )

    if not results:
        raise ValueError(f"No valid rows parsed from {csv_path}")
    return results


def parse_bool(value: object) -> bool | None:
    """Coerce a JSON value into a tristate boolean (True / False / None)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1", "vulnerable", "y"}:
            return True
        if v in {"false", "no", "0", "safe", "not vulnerable", "n"}:
            return False
    return None


def parse_cwe(value: object) -> int | None:
    """Extract an integer CWE id from values like ``"CWE-89"``, ``"89"`` or ``89``."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def category_for_bug_type(bug_type: str) -> str | None:
    """Map a free-text ``bug_type`` to a canonical category code, or ``None``."""
    if not bug_type:
        return None
    needle = bug_type.strip().lower()
    for code, aliases in CATEGORY_ALIASES.items():
        if needle in aliases:
            return code
    # Loose containment fallback (e.g. "Possible SQL Injection in line 42").
    for code, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if len(alias) > 4 and alias in needle:
                return code
    return None

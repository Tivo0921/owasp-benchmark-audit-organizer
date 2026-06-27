#!/usr/bin/env python3
"""Select an experiment subset of OWASP Benchmark testcases.

Reads the organizer answer key (``organizer/expected/expectedresults-1.2.csv``)
and chooses a small, balanced subset of testcases for the experiment.

First-run selection policy (deterministic, fixed seed):

* Mix true vulnerabilities and false positives.
* Keep CWE / category balanced (do not over-represent one category).
* Prioritise SQL Injection, XSS, Command Injection, Path Traversal, Weak Hash
  and LDAP Injection.
* Reproducible: a fixed RNG seed makes the selection stable across runs.

Output: ``organizer/selected_cases.csv`` with at least the columns::

    test_name,category,real_vulnerability,cwe

Usage::

    python scripts/select_cases.py                # 20 cases, seed 42
    python scripts/select_cases.py --count 30 --seed 7
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict

from benchmark_common import (
    CATEGORY_DISPLAY_NAME,
    EXPECTED_CSV,
    PRIORITY_CATEGORIES,
    SELECTED_CASES_CSV,
    ExpectedResult,
    parse_expected_results,
)

DEFAULT_COUNT = 20
DEFAULT_SEED = 42


def _quota_per_category(total: int, categories: list[str]) -> dict[str, int]:
    """Spread ``total`` selections as evenly as possible across ``categories``."""
    base, remainder = divmod(total, len(categories))
    quota: dict[str, int] = {}
    for index, cat in enumerate(categories):
        quota[cat] = base + (1 if index < remainder else 0)
    return quota


def select_cases(
    results: list[ExpectedResult],
    count: int,
    seed: int,
    categories: list[str],
) -> list[ExpectedResult]:
    """Pick a balanced, true/false-mixed subset of ``count`` cases.

    Selection is fully determined by ``seed`` for reproducibility.
    """
    rng = random.Random(seed)

    # Bucket priority-category rows by (category, real_vulnerability).
    by_cat: dict[str, dict[bool, list[ExpectedResult]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for item in results:
        if item.category in categories:
            by_cat[item.category][item.real_vulnerability].append(item)

    available = [c for c in categories if by_cat.get(c)]
    if not available:
        raise ValueError("None of the priority categories were found in the answer key.")

    # Deterministic shuffle of each bucket.
    for cat in available:
        for flag in (True, False):
            rng.shuffle(by_cat[cat][flag])

    quota = _quota_per_category(count, available)
    selected: list[ExpectedResult] = []
    seen: set[str] = set()

    # First pass: honour per-category quota, splitting roughly half true / half
    # false so each category contributes both a real bug and a false positive.
    for cat in available:
        q = quota[cat]
        n_false = q // 2
        n_true = q - n_false
        picks: list[ExpectedResult] = []
        picks += by_cat[cat][True][:n_true]
        picks += by_cat[cat][False][:n_false]
        # Backfill within the category if one flag is short.
        if len(picks) < q:
            leftover = by_cat[cat][True][n_true:] + by_cat[cat][False][n_false:]
            picks += leftover[: q - len(picks)]
        for item in picks:
            if item.test_name not in seen:
                seen.add(item.test_name)
                selected.append(item)

    # Second pass: top up to exactly `count` from any remaining priority rows,
    # alternating true/false to preserve the mix.
    pool_true = [r for c in available for r in by_cat[c][True] if r.test_name not in seen]
    pool_false = [r for c in available for r in by_cat[c][False] if r.test_name not in seen]
    rng.shuffle(pool_true)
    rng.shuffle(pool_false)
    toggle = True
    while len(selected) < count and (pool_true or pool_false):
        pool = pool_true if (toggle and pool_true) or not pool_false else pool_false
        item = pool.pop()
        if item.test_name not in seen:
            seen.add(item.test_name)
            selected.append(item)
        toggle = not toggle

    # Stable, human-friendly ordering by test name.
    selected.sort(key=lambda r: r.test_name)
    return selected[:count]


def write_selected(selected: list[ExpectedResult]) -> None:
    SELECTED_CASES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SELECTED_CASES_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["test_name", "category", "real_vulnerability", "cwe"])
        for item in selected:
            writer.writerow(
                [
                    item.test_name,
                    item.category,
                    "true" if item.real_vulnerability else "false",
                    item.cwe,
                ]
            )


def _print_summary(selected: list[ExpectedResult]) -> None:
    by_cat: dict[str, list[ExpectedResult]] = defaultdict(list)
    for item in selected:
        by_cat[item.category].append(item)
    n_true = sum(1 for r in selected if r.real_vulnerability)
    print(f"[ok] selected {len(selected)} cases "
          f"({n_true} true vulnerabilities, {len(selected) - n_true} false positives)")
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        t = sum(1 for r in rows if r.real_vulnerability)
        name = CATEGORY_DISPLAY_NAME.get(cat, cat)
        print(f"     {cat:<12} {name:<22} total={len(rows):<2} true={t} false={len(rows) - t}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=DEFAULT_COUNT, help="number of cases to select"
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="RNG seed for reproducibility"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.count <= 0:
        print("[error] --count must be positive", file=sys.stderr)
        return 2
    try:
        results = parse_expected_results(EXPECTED_CSV)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    try:
        selected = select_cases(results, args.count, args.seed, PRIORITY_CATEGORIES)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    write_selected(selected)
    _print_summary(selected)
    print(f"[ok] wrote {SELECTED_CASES_CSV}")
    print("Next: python scripts/prepare_public_benchmark.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

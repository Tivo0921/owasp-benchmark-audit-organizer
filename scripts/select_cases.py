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

    python scripts/select_cases.py                       # 20 cases, 50/50
    python scripts/select_cases.py --count 30 --seed 7
    # 100 cases, 10 vulnerable / 90 safe, to a custom file:
    python scripts/select_cases.py --count 100 --true-ratio 0.1 \\
        --out organizer/selected_cases_vuln10.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

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
DEFAULT_TRUE_RATIO = 0.5


def _round_robin(
    buckets: dict[str, list[ExpectedResult]],
    available: list[str],
    total: int,
    seen: set[str],
) -> list[ExpectedResult]:
    """Pick ``total`` items, cycling categories so the spread stays even.

    ``buckets`` maps category -> a pre-shuffled list. ``seen`` tracks already
    chosen test names (shared across true/false passes to avoid duplicates).
    Stops early if the buckets are exhausted before reaching ``total``.
    """
    picked: list[ExpectedResult] = []
    idx = {cat: 0 for cat in available}
    progressed = True
    while len(picked) < total and progressed:
        progressed = False
        for cat in available:
            if len(picked) >= total:
                break
            lst = buckets[cat]
            while idx[cat] < len(lst):
                item = lst[idx[cat]]
                idx[cat] += 1
                if item.test_name not in seen:
                    seen.add(item.test_name)
                    picked.append(item)
                    progressed = True
                    break
    return picked


def select_cases(
    results: list[ExpectedResult],
    count: int,
    seed: int,
    categories: list[str],
    true_ratio: float = DEFAULT_TRUE_RATIO,
) -> list[ExpectedResult]:
    """Pick ``count`` cases at a target vulnerable/safe ratio, category-balanced.

    ``true_ratio`` is the fraction of cases that are true vulnerabilities
    (0.0 .. 1.0); e.g. 0.1 -> 10 vulnerable / 90 safe out of 100. Selection is
    fully determined by ``seed`` for reproducibility.
    """
    if not 0.0 <= true_ratio <= 1.0:
        raise ValueError("true_ratio must be between 0.0 and 1.0")

    rng = random.Random(seed)
    n_true = round(count * true_ratio)
    n_false = count - n_true

    by_true: dict[str, list[ExpectedResult]] = {c: [] for c in categories}
    by_false: dict[str, list[ExpectedResult]] = {c: [] for c in categories}
    for item in results:
        if item.category in categories:
            (by_true if item.real_vulnerability else by_false)[item.category].append(item)

    available = [c for c in categories if by_true[c] or by_false[c]]
    if not available:
        raise ValueError("None of the priority categories were found in the answer key.")

    for cat in available:
        rng.shuffle(by_true[cat])
        rng.shuffle(by_false[cat])

    seen: set[str] = set()
    selected = _round_robin(by_true, available, n_true, seen)
    selected += _round_robin(by_false, available, n_false, seen)

    # Stable, human-friendly ordering by test name.
    selected.sort(key=lambda r: r.test_name)
    return selected


def write_selected(selected: list[ExpectedResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
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
    parser.add_argument(
        "--true-ratio",
        type=float,
        default=DEFAULT_TRUE_RATIO,
        help="fraction of cases that are true vulnerabilities, 0..1 "
        "(e.g. 0.1 = 10 vulnerable / 90 safe)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SELECTED_CASES_CSV,
        help="output CSV path (default: organizer/selected_cases.csv)",
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
        selected = select_cases(
            results, args.count, args.seed, PRIORITY_CATEGORIES, args.true_ratio
        )
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if len(selected) < args.count:
        print(
            f"[warn] only {len(selected)}/{args.count} cases available at the "
            f"requested ratio (true_ratio={args.true_ratio}); not enough rows in "
            "some category/flag buckets.",
            file=sys.stderr,
        )

    write_selected(selected, args.out)
    _print_summary(selected)
    print(f"[ok] wrote {args.out}")
    print("Next: python scripts/prepare_public_benchmark.py --selected "
          f"{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

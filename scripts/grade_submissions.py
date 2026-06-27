#!/usr/bin/env python3
"""Grade participant JSON submissions against the OWASP Benchmark answer key.

Input layout::

    submissions/
      team_or_model_name/
        BenchmarkTest00001.json
        BenchmarkTest00002.json
        ...

Each JSON follows ``benchmark/public/report_template.json``. The test name is
taken from the JSON ``test_name`` field, falling back to the file stem.

Scoring (3 points per case):

* ``is_vulnerable``           -> 1 point if it matches the ground truth
* ``cwe``                     -> 1 point if the CWE id matches
* ``bug_type`` / ``category`` -> 1 point if it maps to the correct category

Ground truth comes from ``organizer/expected/expectedresults-1.2.csv``.

Output: ``results/score_summary.csv`` with columns::

    team,model_or_agent,model_name,total_cases,total_score,max_score,
    vulnerability_accuracy,cwe_accuracy,category_accuracy

Usage::

    python scripts/grade_submissions.py
    python scripts/grade_submissions.py --submissions submissions --out results/score_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from benchmark_common import (
    CATEGORY_TO_CWE,
    EXPECTED_CSV,
    RESULTS_DIR,
    SCORE_SUMMARY_CSV,
    SUBMISSIONS_DIR,
    ExpectedResult,
    category_for_bug_type,
    parse_bool,
    parse_cwe,
    parse_expected_results,
)

POINTS_PER_CASE = 3


@dataclass
class TeamScore:
    team: str
    model_or_agent: str
    model_name: str
    total_cases: int = 0
    total_score: int = 0
    vuln_correct: int = 0
    cwe_correct: int = 0
    category_correct: int = 0

    @property
    def max_score(self) -> int:
        return self.total_cases * POINTS_PER_CASE

    def _ratio(self, n: int) -> float:
        return round(n / self.total_cases, 4) if self.total_cases else 0.0

    @property
    def vulnerability_accuracy(self) -> float:
        return self._ratio(self.vuln_correct)

    @property
    def cwe_accuracy(self) -> float:
        return self._ratio(self.cwe_correct)

    @property
    def category_accuracy(self) -> float:
        return self._ratio(self.category_correct)


def load_truth(expected_csv: Path) -> dict[str, ExpectedResult]:
    return {r.test_name: r for r in parse_expected_results(expected_csv)}


def _load_json(path: Path) -> dict[str, object] | None:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[warn] could not read {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"[warn] {path} is not a JSON object -- skipping", file=sys.stderr)
        return None
    return data


def grade_case(
    submission: dict[str, object], truth: ExpectedResult
) -> tuple[int, bool, bool, bool]:
    """Score one submission against ground truth. Returns (points, vuln, cwe, category)."""
    # 1) is_vulnerable
    sub_vuln = parse_bool(submission.get("is_vulnerable"))
    vuln_ok = sub_vuln is not None and sub_vuln == truth.real_vulnerability

    # 2) cwe
    sub_cwe = parse_cwe(submission.get("cwe"))
    cwe_ok = sub_cwe is not None and sub_cwe == truth.cwe

    # 3) bug_type / category. Accept an explicit bug_type/category string, or a
    #    correct CWE as evidence of the right category.
    bug_type = str(submission.get("bug_type") or submission.get("category") or "")
    mapped = category_for_bug_type(bug_type)
    category_ok = mapped == truth.category
    if not category_ok and sub_cwe is not None:
        category_ok = CATEGORY_TO_CWE.get(truth.category) == sub_cwe

    points = int(vuln_ok) + int(cwe_ok) + int(category_ok)
    return points, vuln_ok, cwe_ok, category_ok


def _pick_metadata(team_dir: Path) -> tuple[str, str]:
    """Determine the most common model_or_agent / model_name across a team's files."""
    agents: Counter[str] = Counter()
    models: Counter[str] = Counter()
    for json_path in sorted(team_dir.glob("*.json")):
        data = _load_json(json_path)
        if data is None:
            continue
        agent = str(data.get("model_or_agent") or "").strip()
        model = str(data.get("model_name") or "").strip()
        if agent:
            agents[agent] += 1
        if model:
            models[model] += 1
    agent = agents.most_common(1)[0][0] if agents else ""
    model = models.most_common(1)[0][0] if models else ""
    return agent, model


def grade_team(team_dir: Path, truth: dict[str, ExpectedResult]) -> TeamScore | None:
    json_files = sorted(team_dir.glob("*.json"))
    if not json_files:
        print(f"[warn] no JSON submissions in {team_dir} -- skipping", file=sys.stderr)
        return None

    agent, model = _pick_metadata(team_dir)
    score = TeamScore(team=team_dir.name, model_or_agent=agent, model_name=model)

    for json_path in json_files:
        data = _load_json(json_path)
        if data is None:
            continue
        test_name = str(data.get("test_name") or "").strip() or json_path.stem
        ground = truth.get(test_name)
        if ground is None:
            print(f"[warn] {team_dir.name}/{json_path.name}: "
                  f"test '{test_name}' not in answer key -- skipping", file=sys.stderr)
            continue
        points, vuln_ok, cwe_ok, cat_ok = grade_case(data, ground)
        score.total_cases += 1
        score.total_score += points
        score.vuln_correct += int(vuln_ok)
        score.cwe_correct += int(cwe_ok)
        score.category_correct += int(cat_ok)

    return score if score.total_cases else None


def write_summary(scores: list[TeamScore], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "team",
            "model_or_agent",
            "model_name",
            "total_cases",
            "total_score",
            "max_score",
            "vulnerability_accuracy",
            "cwe_accuracy",
            "category_accuracy",
        ])
        for s in sorted(scores, key=lambda x: x.total_score, reverse=True):
            writer.writerow([
                s.team,
                s.model_or_agent,
                s.model_name,
                s.total_cases,
                s.total_score,
                s.max_score,
                s.vulnerability_accuracy,
                s.cwe_accuracy,
                s.category_accuracy,
            ])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=Path, default=SUBMISSIONS_DIR,
                        help="submissions root directory")
    parser.add_argument("--expected", type=Path, default=EXPECTED_CSV,
                        help="path to expectedresults-1.2.csv")
    parser.add_argument("--out", type=Path, default=SCORE_SUMMARY_CSV,
                        help="output score summary CSV")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        truth = load_truth(args.expected)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if not args.submissions.is_dir():
        print(f"[error] submissions directory not found: {args.submissions}", file=sys.stderr)
        return 1

    team_dirs = sorted(d for d in args.submissions.iterdir() if d.is_dir())
    if not team_dirs:
        print(f"[error] no team subdirectories under {args.submissions}", file=sys.stderr)
        return 1

    scores: list[TeamScore] = []
    for team_dir in team_dirs:
        result = grade_team(team_dir, truth)
        if result is not None:
            scores.append(result)
            print(f"[ok] {result.team}: {result.total_score}/{result.max_score} "
                  f"(vuln={result.vulnerability_accuracy} "
                  f"cwe={result.cwe_accuracy} category={result.category_accuracy})")

    if not scores:
        print("[error] no gradable submissions found.", file=sys.stderr)
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_summary(scores, args.out)
    print(f"\n[ok] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

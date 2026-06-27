# Organizer Guide

This guide walks through running one evaluation round end-to-end.

## 0. Prerequisites

- Python 3.12+ and `git` installed.
- A private place to keep `organizer/` (it holds the answer key).

## 1. Obtain OWASP BenchmarkJava

```bash
python scripts/download_owasp_benchmark.py
```

This will:

1. `git clone https://github.com/OWASP-Benchmark/BenchmarkJava.git
   third_party/BenchmarkJava` **only if** it does not already exist (an existing
   clone is reused, not re-cloned),
2. copy `expectedresults-1.2.csv` into `organizer/expected/`,
3. verify the Java testcases directory and report the case count.

`third_party/` is git-ignored, so the external repo is never committed here. If
the automatic clone fails (e.g. no network), the script prints manual clone
instructions:

```bash
git clone https://github.com/OWASP-Benchmark/BenchmarkJava.git third_party/BenchmarkJava
python scripts/download_owasp_benchmark.py
```

## 2. Select cases

```bash
python scripts/select_cases.py            # 20 cases, seed 42 (default)
# or tune:
python scripts/select_cases.py --count 30 --seed 7
```

Selection policy:

- mixes **true vulnerabilities** and **false positives**,
- balances across categories,
- prioritises SQL Injection, XSS, Command Injection, Path Traversal, Weak Hash,
  LDAP Injection,
- is **deterministic** for a given `--seed` (reproducible rounds).

Output: `organizer/selected_cases.csv` (columns
`test_name,category,real_vulnerability,cwe`). This file contains labels — keep
it private.

## 3. Build the public benchmark

```bash
python scripts/prepare_public_benchmark.py
```

This copies only the selected `.java` files into `benchmark/public/cases/` and
(re)writes `report_template.json` and the public `README.md`. It explicitly does
**not** copy the answer key, anything under `organizer/`, scorecards, or any
label-bearing file. The `benchmark/public/` folder is what you distribute.

> Tip: before sharing, sanity-check that no labels leaked:
> ```bash
> grep -rl "expectedresults\|real_vulnerability" benchmark/public && echo LEAK || echo clean
> ```

## 4. Collect submissions

Ask each team/model to drop their JSON files under:

```text
submissions/<team_or_model_name>/BenchmarkTestNNNNN.json
```

## 5. Grade

```bash
python scripts/grade_submissions.py
cat results/score_summary.csv
```

Each case is worth 3 points (`is_vulnerable`, `cwe`, `bug_type`/category).
Output: `results/score_summary.csv` with per-team totals and per-dimension
accuracy.

## Critical: integrity comes from sandboxing the agent, not from secrecy

The OWASP Benchmark answer key is **already public** upstream, and this repo is
published openly so participants can self-grade. So validity does **not** rest
on hiding `expectedresults-1.2.csv`. It rests on the **evaluated agent not
looking anything up during the run**:

- **Web search / browsing off** (the distributed repo ships a Claude Code
  `.claude/settings.json` denying `WebSearch`/`WebFetch`).
- **File access scoped to the `cases/` folder only** — the agent must not open
  this organizer repo, sibling directories, or the upstream OWASP repo.
- Run each evaluated agent in a **fresh, isolated session** seeded only with the
  distributed cases.

If you publish a leaderboard, **re-grade the submissions yourself** instead of
trusting self-reported scores.

## Critical: separate the benchmark-building AI from the evaluated AI

Use a **different AI session/account** to build the benchmark than the one you
later evaluate, so the evaluated agent is never contaminated by the answer key
or selection through shared context:

- Do the download/select/prepare steps in one session.
- Run each evaluated agent in a fresh, sandboxed session that only sees the
  distributed `cases/`.

## Re-running / new rounds

Change `--seed` (and/or `--count`) in step 2 and re-run steps 2–3 to produce a
fresh, reproducible case set. Record the seed used for each round.

# OWASP BenchmarkJava — AI Code-Audit Evaluation Harness

A small, stable harness for comparing how well **AI coding agents audit code**.
Agents read individual Java vulnerability testcases from
[OWASP BenchmarkJava](https://github.com/OWASP-Benchmark/BenchmarkJava) and
produce a structured JSON vulnerability report per case. The harness then grades
those reports against the official answer key.

This is **not** a flag-capture or exploit-writing contest. It is a *static
code-audit* evaluation. For each case we measure whether an agent can:

- decide whether a vulnerability is present (`is_vulnerable`),
- name the vulnerability category (`bug_type`),
- identify the CWE (`cwe`),
- explain the root cause, and
- propose a fix.

We deliberately scope to **OWASP BenchmarkJava only** (not CRSBench / SECCON /
Juliet) to keep the harness stable and reproducible. No web app is deployed and
no DAST is run — everything is answerable by reading the code.

## Why this design

- **Answer key stays private.** `expectedresults-1.2.csv` lives only under
  `organizer/` and is never copied into the participant-facing folder.
- **Participants get code only.** They receive the selected `.java` files plus a
  JSON report template — nothing that reveals the ground-truth label.
- **Grading is mechanical.** Submitted JSON is compared field-by-field to the
  answer key.

## Repository layout

```text
.
├── README.md
├── pyproject.toml
├── docs/
│   ├── participant-guide.md      # rules for participants
│   ├── organizer-guide.md        # how to run a round
│   └── experiment-design.md      # closed-book / open-book / RAG conditions
├── benchmark/
│   ├── public/                   # SAFE TO DISTRIBUTE (generated)
│   │   ├── cases/                # selected BenchmarkTestNNNNN.java
│   │   └── report_template.json
│   └── README.md
├── organizer/                    # ORGANIZER ONLY — do not share
│   ├── expected/
│   │   └── expectedresults-1.2.csv
│   ├── selected_cases.csv
│   └── README.md
├── submissions/                  # participant JSON submissions land here
├── results/                      # generated score_summary.csv
├── scripts/
│   ├── benchmark_common.py       # shared constants / parsing
│   ├── download_owasp_benchmark.py
│   ├── select_cases.py
│   ├── prepare_public_benchmark.py
│   └── grade_submissions.py
└── third_party/                  # cloned BenchmarkJava (git-ignored)
```

## Requirements

- Python **3.12+** (standard library only — no pip install needed to run).
- `git` on PATH (for the download step).
- Optional dev tooling: `pip install -e ".[dev]"` for `ruff` + `black`.

## Quick start (organizer)

```bash
# 1. Fetch OWASP BenchmarkJava and stage the (private) answer key.
python scripts/download_owasp_benchmark.py

# 2. Select a balanced 20-case subset (deterministic, fixed seed).
python scripts/select_cases.py

# 3. Build the participant-facing public benchmark (code + template only).
python scripts/prepare_public_benchmark.py

# 4. After collecting submissions, grade them.
python scripts/grade_submissions.py
cat results/score_summary.csv
```

Distribute the contents of `benchmark/public/` to participants. Keep
`organizer/` and `third_party/` private.

## Scoring

Each case is worth **3 points**:

| Field                  | Points | Correct when …                              |
| ---------------------- | ------ | ------------------------------------------- |
| `is_vulnerable`        | 1      | matches the answer key (true/false)         |
| `cwe`                  | 1      | the CWE id matches                          |
| `bug_type` / category  | 1      | maps to the correct OWASP Benchmark category|

`results/score_summary.csv` columns:

```text
team,model_or_agent,model_name,total_cases,total_score,max_score,
vulnerability_accuracy,cwe_accuracy,category_accuracy
```

## Submissions format

One JSON file per case, named after the test (e.g.
`BenchmarkTest00027.json`), following `benchmark/public/report_template.json`:

```text
submissions/
  <team_or_model_name>/
    BenchmarkTest00027.json
    BenchmarkTest00294.json
    ...
```

A worked dummy submission lives in `submissions/dummy-model/` so you can confirm
the grader runs before a real round.

## Documentation

- [`docs/participant-guide.md`](docs/participant-guide.md) — what participants do.
- [`docs/organizer-guide.md`](docs/organizer-guide.md) — running a round safely.
- [`docs/experiment-design.md`](docs/experiment-design.md) — evaluation conditions.

## Notes & limitations

OWASP Benchmark is a *synthetic* benchmark. Strong scores here indicate solid
**baseline code-audit ability**, not direct real-world OSS bug-bounty
performance. See `docs/experiment-design.md` for positioning.

The OWASP Benchmark source is licensed GPL-2.0 and is cloned into
`third_party/` (git-ignored) — it is not redistributed by this repository.

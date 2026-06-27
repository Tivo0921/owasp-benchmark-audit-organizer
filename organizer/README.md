# organizer/ — answer key & grading inputs

This directory holds the ground-truth answer key and the per-round selection
used for grading.

## Important: secrecy is NOT the integrity mechanism

The OWASP Benchmark answer key (`expectedresults-1.2.csv`) is **already publicly
available** in the upstream project, so this repository is published openly to
let participants self-grade. **The validity of a closed-book result does not
depend on the answers being secret** — it depends on the **evaluated agent not
looking anything up during the run**:

- web search / browsing **off**, and
- file access scoped to the distributed `cases/` only (no access to this repo).

See `docs/experiment-design.md` and the participant guide's *Web search rule*.

## Contents

- `expected/expectedresults-1.2.csv` — the official OWASP Benchmark answer key
  (GPL-2.0), staged by `scripts/download_owasp_benchmark.py`. Ground truth for
  grading.
- `selected_cases.csv` — the cases chosen for the current round
  (`scripts/select_cases.py`). Columns:
  `test_name,category,real_vulnerability,cwe`.
- `selected_cases_pilot20.csv` — record of the 20-case pilot round.

## Reminders

- Build the benchmark in a **different AI session** from any agent you evaluate,
  and run each evaluated agent **sandboxed** (no web, only the `cases/` folder).
- For an official leaderboard, **re-grade submissions yourself** rather than
  trusting self-reported scores (self-grading is for convenience/transparency).
- `third_party/` (the upstream clone) stays git-ignored — never committed.

# organizer/ — ORGANIZER ONLY (do not distribute)

Everything in this directory is private to the organizers. **Never** share it
with participants and never copy it into `benchmark/public/`.

## Contents

- `expected/expectedresults-1.2.csv` — the official OWASP Benchmark answer key.
  Staged here by `scripts/download_owasp_benchmark.py`. This is the ground truth
  used for grading. **Keeping this hidden from participants is the single most
  important rule of the experiment.**
- `selected_cases.csv` — the subset chosen for the current round, written by
  `scripts/select_cases.py`. Columns: `test_name,category,real_vulnerability,cwe`.
  It contains labels, so it is organizer-only too.

## Reminders

- Run the benchmark-building work (selection, packaging) in a **different AI
  session / account** from any agent you later evaluate, so an evaluated agent
  never sees the answer key or selection through shared context.
- If you commit this repository, confirm `benchmark/public/` contains no labels
  and that `third_party/` is git-ignored. The answer key under `organizer/`
  may be committed to a *private* repo only.

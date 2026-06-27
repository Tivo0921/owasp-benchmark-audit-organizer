# Experiment Design

## Goal

Measure the **baseline code-audit ability** of AI coding agents: given a single
Java file, can the agent correctly judge vulnerability presence, category, CWE,
root cause, and fix? We use OWASP BenchmarkJava because it provides a large,
labelled set of true vulnerabilities and matched false positives.

## What we measure (per case)

| Dimension       | Field          | Scored |
| --------------- | -------------- | ------ |
| Vulnerable?     | `is_vulnerable`| ✅ 1 pt |
| CWE             | `cwe`          | ✅ 1 pt |
| Category        | `bug_type`     | ✅ 1 pt |
| Root cause      | `root_cause`   | recorded (qualitative) |
| Fix strategy    | `patch_strategy`| recorded (qualitative) |

The automated grader scores the three objective dimensions (3 pts/case). Root
cause and fix strategy are captured for qualitative review and future rubrics.

## Evaluation conditions

### Closed-book (default for this harness)

- **Web search / browsing: disabled.**
- The agent sees only the distributed Java code in `benchmark/public/cases/`.
- Tests the model's intrinsic audit ability without external lookup.
- Reports must set `"web_search_used": false`.

This is the **primary** condition. We start here because it is the most stable
to run and the easiest to compare across agents.

### Open-book (optional, for comparison)

- **Web search / browsing: allowed.**
- The agent may consult external references (CWE pages, docs, write-ups).
- Reports must set `"web_search_used": true` so results are separable from the
  closed-book condition.
- Treated as a *reference* condition, run only when explicitly enabled.

### RAG (future work)

- A **curated, limited** corpus (e.g. selected CWE descriptions, secure-coding
  notes) is provided to the agent via retrieval — no open web.
- Lets us study how much targeted reference material helps, without the
  uncontrolled variance of open web search.
- Not implemented in this round; reserved as a planned extension.

## Why closed-book first

For stable, repeatable runs we keep the default **closed-book**: no web app
execution, no DAST, no external search. Every case is answerable purely by
reading the code, which removes networking, environment, and crawl-variance from
the results and makes scores reproducible across agents and rounds.

## Case selection

- Deterministic (fixed RNG seed) for reproducibility.
- Mixes true vulnerabilities with false positives so agents cannot win by always
  answering "vulnerable".
- Balanced across categories, prioritising SQL Injection, XSS, Command
  Injection, Path Traversal, Weak Hash, and LDAP Injection.

## Positioning & limitations

OWASP Benchmark is a **synthetic** benchmark: testcases are generated from
templates and are simpler and more uniform than real-world code. Therefore:

- Results indicate **baseline static code-audit competence**, not a direct
  measurement of real-world OSS bug-bounty capability.
- High scores here are necessary-but-not-sufficient for real audit work; they do
  not prove an agent can find novel bugs in large, messy codebases.
- The matched true/false-positive design specifically probes whether an agent
  can avoid false alarms, which is a meaningful and often-overlooked skill.

We position this harness as the **first, stable rung**: a controlled, reproducible
baseline that later, more realistic evaluations (real OSS, RAG, open-book) can
build on.

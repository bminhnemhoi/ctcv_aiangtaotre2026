---
name: ctcv-parallel-plan-without-git
description: How to split CTCV work across parallel subagents when the repo has no commits (no worktrees) — contract-first package, disjoint file ownership, known test traps
metadata:
  type: project
---
Until the user makes the first commit, the repo has no git history, so subagents cannot use worktrees and all of them edit the same tree. As of 2026-09-25, the plan for this situation is:
- Run a short "contracts" package first. It writes the shared Pydantic models and protocols (ctcv_agent/contracts.py and rag/types.py), together with fakes, the config/rag.yaml file and its schema, and test fixtures. The index, answer-engine and API packages then run in parallel against those fakes.
- Give each package an exact `files_owned` list. Two packages may own the same file only if they run one after the other.
- Each agent runs only its own test files. Integration is its own package, run by devops, followed by a qa-tester gate. Stay at 5 or fewer concurrent packages.

Test traps found while planning (all of these must be edited when the related feature ships; never delete them):
- `data/tests/test_cli.py::test_unimplemented_steps_exit_zero` asserts that normalize, chunk_embed and build_eval_sets are still stubs.
- `test_all_steps_run_in_order` runs every pipeline step against the real repo root. Steps therefore need a clean-dir override, and any step that calls a model must require `--online`.
- `services/api/tests/test_contract.py` pins the 16 OpenAPI paths and expects `/v1/coach/ask` to return 501.
- `tests/config/test_prompts.py` pins the set of prompt files.
- `tests/invariants/test_no_pii.py` scans `eval/sets/samples/*.jsonl`, so attack questions containing PII-shaped digits belong in `eval/redteam/`.
- `make check` includes `make integration`, so model- or Ollama-dependent checks must live in the `make eval` suites, not in pytest `integration` tests.

**Why:** there is no rollback without git, and a half-written module can break other packages' imports.

**How to apply:**
- Reuse this structure for any multi-agent epic until worktrees are available.
- Recommend that the user commit first.

Related: [[dfl-pivot-2026-09-25]]

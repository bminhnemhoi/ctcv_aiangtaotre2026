---
name: prepublish-state-2026-09-25
description: Outcome of the 2026-09-25 pre-publish audit (repo going public for Data for Life) — what must be re-verified on the next audit
metadata:
  type: project
---

Audit 2026-09-25 (report `docs/security/2026-09-25-pre-publish.md`) said: do NOT publish as-is.

- Old raw session transcripts under `docs/prompt-log/` (and the local export zip of 19/9) hold sensitive
  data of the owner and of another project; gitleaks does not see part of it. Owner was asked to rotate.
- Orchestrator switched `.gitignore` to option (b) the same day (raw `sessions/`, `subagents/`, `system/`
  ignored; `.playwright-mcp/`, `ctcv-dev.db` ignored); `.gitignore` line `build/` also hides
  `docs/dossier/build/**` (scripts + tests) from the repo.
- Recommended prompt-log policy for the public repo: publish only `INDEX.md` + README (hashes), keep raw
  transcripts private, share with organisers on request. The old "never ignore docs/prompt-log" rule came
  from Bảng C (dropped); DFL does not require public prompt logs.
- `.claude/BOOTSTRAP` was still present (protect-paths relaxed).

**Why:** user wants the public GitHub link as the DFL "link dùng thử" (deadline 25/9).

**How to apply:** on the next audit or PR touching publishing, verify: credential rotated (ask user), raw
transcripts absent from `git ls-files`, BOOTSTRAP gone, export redaction fixed + regression tests present,
`.gitleaks.toml` has a URL-credential rule. Related: [[prepublish-audit-patterns]], [[mask-before-print]].

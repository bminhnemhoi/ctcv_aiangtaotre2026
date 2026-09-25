---
name: mask-before-print
description: In audits never print raw context windows around credential-like matches; mask structurally first, because every tool output of this agent is copied into docs/prompt-log/subagents/
metadata:
  type: feedback
---

Never print a raw text window around a credential-like match (URL userinfo, JSON value of `*password*`,
`*token*`, `?lop=`). Compute and print only derived facts: length, class (placeholder / test / real-looking),
2-character prefix, file and line.

**Why:** 2026-09-25 pre-publish audit — a context print around a DB connection string taken from an export
that had already been partially redacted: the mask regex relied on the `@`, the redaction token had eaten the
`@`, so 14 characters of a real password went into this agent's own transcript. The promptlog/subagent-log
hooks copy that transcript into `docs/prompt-log/subagents/`, i.e. into the repo.

**How to apply:** write analysis scripts that replace the whole matched value (not a regex-derived sub-part)
before printing; treat already-redacted files as untrusted input for masking; if a leak into the transcript
happens anyway, disclose it in the report and add "rotate + do not publish raw prompt-log" to blockers.
Related: [[prepublish-audit-patterns]].

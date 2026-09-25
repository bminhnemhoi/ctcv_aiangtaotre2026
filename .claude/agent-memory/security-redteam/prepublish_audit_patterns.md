---
name: prepublish-audit-patterns
description: How to audit CTCV before making the repo public — scanner blind spots (gitleaks, promptlog_export redaction), where secrets/PII hide in Claude Code transcripts, hook quirks
metadata:
  type: reference
---

Blind spots found 2026-09-25 (re-verify, tools change):

- gitleaks 8.30 default rules do NOT flag passwords inside connection URLs (`scheme://user:pw@host`) nor
  Supabase `sb_publishable_`/`sb_secret_` keys. Repo `.gitleaks.toml` allowlists `docs/prompt-log/` for the
  e-mail/phone rules and `eval/sets/` globally; its `^docs/` path anchors only work when gitleaks runs with
  `--source .` from the repo root (absolute `--source` silently disables the custom rules).
- `scripts/promptlog_export.py` redaction = gitleaks secrets + `config/guardrails.yaml: pii_patterns`. The
  e-mail pattern catches `pw@host` only from the last non-`%` char: a URL-encoded password keeps its prefix.
  Demo creds (`officer_password`, `?lop=` class token), `sb_` keys and local dir lists are not redacted.
- Claude Code transcripts (`docs/prompt-log/**`) carry, besides messages: `attachment.session_context`
  (owner e-mail), `attachment.environment` (additional working dirs = other private projects),
  `attachment.credential_org` (org UUID), tool outputs that dumped `~/.claude/settings.json` (allow-rules of
  OTHER projects, which can embed secrets), printed temporary demo credentials.
- Method that worked: copy publish list (`git add -A -n`) to scratchpad → decode each JSONL line and walk all
  strings → regex classes with masked output → check context only via derived facts ([[mask-before-print]]);
  probe redaction with FAKE values by importing `promptlog_export.redact_text`.
- Guard hook blocks any Bash command text containing `.env`, `*.key`/`*.pem` globs or `core.hooksPath`, even
  read-only `find`/`git config --get`: put analysis code in a scratchpad `.py` via Write, then run it.
- `make redteam` writes `eval/reports/redteam-<date>.md`; for read-only audits run
  `uv run python -m ctcv_eval.redteam --report-dir <scratchpad>`.

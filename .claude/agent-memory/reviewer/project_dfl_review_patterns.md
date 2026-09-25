---
name: dfl-review-patterns
description: Recurring defects found reviewing the DFL 2026 (DA940-01) TTHC RAG work — hardware claims, eval ablation bias, dossier claim/test mismatches, gitleaks on test fixtures
metadata:
  type: project
---

Patterns seen in the 2026-09-25 DFL review (ADR-007). Re-check them on every later DFL/RAG diff.

- **CPU vs GPU claims**: Ollama auto-offloads to the RTX 4050 Laptop (env-tthc.json gpu_offload_pct 100), yet docs keep saying "CPU, không GPU" (services/agent/README, docs/ops/cpu-demo.md, ADR-007, QA report). Grep for "không GPU"/"chỉ CPU" in every diff.
- **Quantization**: Ollama qwen3.5:2b is Q8_0; models.yaml/CLAUDE.md say Q4_K_M. Dossier must declare what was measured.
- **Ablation scoring**: eval/suites/qa.py `_unverified` took `retrieved_procedure_ids[0]` while the engine routes to a local "twin" procedure (ask.py `_local_twin`) → llm_unverified answer_accuracy understated. Check that every ablation mode scores against the same routed procedure.
- **numeric.py**: "<n> triệu/nghìn" accepted when bare n appears anywhere in source ("7 triệu" vouched by "07 ngày").
- **Dossier cites wrong test / understates code** (e.g. says channel-swap not caught while `fee_channel_mismatch` exists). Verify every "(file · test)" pointer.
- **gitleaks** flags fake qr_token/jwt_secret in new tests → audit red beyond the 3 baseline reasons of ADR-008.
- **Evidence**: docs/status/last_check.json stayed at 2026-09-18; use docs/status/qa-*.md + scratchpad logs. Glob returns files by mtime — useful to prove eval/reports/latest.json is newer than engine code.

**Why:** thể lệ DFL cấm làm giả kết quả; user explicitly forbade wrong hardware/quant declarations.
**How to apply:** treat any of these as at least "major" and check them first in DFL reviews. See [[dfl-submission-context]].

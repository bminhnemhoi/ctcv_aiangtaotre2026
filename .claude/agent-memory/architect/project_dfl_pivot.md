---
name: dfl-pivot-2026-09-25
description: CTCV target switched on 2026-09-25 from Sáng tạo trẻ AI (Bảng C) to Data for Life 2026 topic DA940-01; ADR-007 draft decisions and the options rejected, with reasons
metadata:
  type: project
---
On 2026-09-25 the user dropped the Sáng tạo trẻ AI / BTC Bảng C competition and entered Data for Life mùa 4 (Bộ Công an / C06), topic DA940-01 "Mô hình ngôn ngữ lớn tiếng Việt và trợ lý số công dân, công vụ". The round-1 deadline shown on the form is 25/09/2026. Round 1 needs a PDF proposal of at most 10 pages and a video of at most 3 minutes. The rules forbid faking results or demoing features that do not exist.

**Why:** this was the user's explicit choice. The organiser runs VNeID, and the topic asks for RAG over administrative procedures (TTHC), an anti-hallucination layer and in-country inference. That matches CTCV's third invariant (every fact must be cited) and its CPU-only path.

**How to apply:**
- Use docs/competition/DFL-2026-yeu-cau.md as the dossier authority, but only once ADR-007 is "chốt" and CLAUDE.md has been edited through the ADR.
- Take every number from eval/reports. Never show voice or other non-working features in the video or the proposal.

Architect decisions drafted in ADR-007 (still "đề xuất" when this memory was written; check docs/decisions/ before relying on them):
- **TTHC data source.** Use dichvucong.bocongan.gov.vn: it renders server-side and its robots.txt allows crawling. dichvucong.gov.vn was rejected because it is an SPA and robots.txt disallows /assets/.
- **Search index.** Pure-Python BM25 plus bge-m3 (served by Ollama), fused with RRF. qdrant-client, numpy and pypdf were rejected because none is in uv.lock and adding a library is a stop point.
- **Model serving.** Ollama runs the models on the CPU path. config/rag.yaml `serving_aliases` maps Ollama model names to the IDs in models.yaml, and a test enforces the mapping. Editing models.yaml `served_by` was rejected because it is a stop point.
- **Intake check.** Checking a submitted file against the required documents is a deterministic API route (#17, /v1/coach/intake-check), not an agent tool, because adding a tool is a stop point.
- **Demo auth.** Demo login is enabled only by environment variables. It is off by default and refused in prod.
- **Deferred.** N2 (filling forms from identity data) touches invariant 2 and needs its own ADR.

Related: [[ctcv-parallel-plan-without-git]]

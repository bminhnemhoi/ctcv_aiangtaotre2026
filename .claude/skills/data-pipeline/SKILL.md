---
name: data-pipeline
description: Pipeline dữ liệu make data của CTCV (plan §7, 9 bước) — crawl robots-aware, chuẩn hóa, chunk/embed Qdrant, sinh kịch bản và drill, render ảnh UI, hội thoại SFT/DPO qua bộ lọc + LLM-judge, tập đánh giá, registry có giấy phép và sha256. Use when working under data/, sandbox/scenarios, drills/scenarios, eval/sets or data/registry.
---
# `make data` — 9 bước (plan §7; mã ở `data/src/ctcv_data/pipeline/`, mỗi bước một module có test)

| Bước | Đầu vào | Đầu ra | Kiểm soát chất lượng (bắt buộc có test) |
| --- | --- | --- | --- |
| 1. Crawl | `data/sources.yaml` (URL chính thống được duyệt; robots-aware; **1 req/s**) | `data/raw/guides/*.html` + `manifest.jsonl` (url, fetched_at, sha256, license_note) | Bỏ trang không có hướng dẫn; **cảnh báo khi hash đổi** so với lần trước; trong đóng băng: không cập nhật |
| 2. Chuẩn hóa | HTML → Markdown, tách theo bước/mục, gắn cơ quan ban hành + ngày cập nhật | `data/clean/guides/*.md` | Loại trang < 200 từ; kiểm bảng mã tiếng Việt (NFC) |
| 3. Chunk + embed | Markdown | Qdrant `guides_v{n}` (bge-m3 dense + BM25 sparse) | **Recall@5 ≥ 0,9** trên 100 câu hỏi có nhãn |
| 4. Sinh kịch bản | Hướng dẫn + `config/schemas/scenario.schema.json` | `sandbox/scenarios/*.json` (id cố định brief §5; E01 1, E02 4, E10 +…) | Validator máy trạng thái (`ctcv_sandbox.validator`); 30 mẫu duyệt tay (báo cáo HTML) |
| 5. Render ảnh | Kịch bản + Playwright | `data/ui/images/*.png` + `labels/*.json` (khung từ DOM, 6 viewport) | 20.000 ảnh; khung không rỗng; nhãn "Ứng dụng mô phỏng" hiện trong ảnh |
| 6. Sinh hội thoại | 5 persona × kịch bản × `common_mistakes` | `data/sft/train.jsonl`, `data/dpo/pairs.jsonl` | **Bộ lọc ràng buộc** (≤ 2 câu, có hành động, xác nhận ý định lượt đầu, không PII, không `banned_terms`) rồi LLM-judge ≥ 4/5 (`config/eval.yaml: judge`, prompt `judge.v1`) |
| 7. Kịch bản lừa đảo | Cảnh báo công khai (Bộ Công an, NCA) | `drills/scenarios/*.json` | Schema drill (brief §6 + D27): `utterance` **1 lượt ≤ 40 từ** có "[Mô phỏng]", không URL/SĐT/STK/tên ngân hàng-cơ quan thật, không `script/dialogue/message`, không chuỗi > 200 ký tự; **duyệt tay 100 %** |
| 8. Tập đánh giá | Tất cả trên | `eval/sets/` (Q&A 300, hội thoại 500, ảnh 1.500 + 200 thật, red-team 200, audio 10 giờ) | Seed cố định; tách dev/test; checksum vào registry; không tối ưu trên test |
| 9. Registry | Mọi tập | `data/registry/datasets.yaml` | Test schema `config/schemas/datasets-registry.schema.json`; bản kê khai đọc từ đây |

Bản nộp 29/9 (ADR-006): quy mô nhỏ nhưng thật — 50–150 URL, 6 kịch bản, 10 drill, 100 Q&A, 100 hội thoại; số đầy đủ ở Pha D.

## Registry `datasets.yaml[]` (brief §9 + §17.4)
`name`, `version`, `source` (url|synthetic), `source_type`, `license` (SPDX), `license_url`, `tos_url`, `tos_checked_on`, `redistribute` (bool), `derived_from[]`, `generator_model`, `generator_license` (khi synthetic), `collected_at`, `size{records, mb}`, `sha256`, `used_for` (rag|sft|dpo|ui|drill|eval), `pii: none`, `notes`. Giấy phép đã xác minh: Common Voice vi CC0; **VIVOS CC BY-NC-SA 4.0 → chỉ đánh giá, không huấn luyện phát hành**; Qwen3.5 Apache-2.0; PhoWhisper BSD-3-Clause; bge-m3 MIT; YOLOX Apache-2.0.

## Ngân sách và kê khai
- Gọi API LLM để sinh dữ liệu: cập nhật `training/budget.json: next_job.estimated_api_vnd` trước; **> 500.000 đ/tác vụ → dừng, hỏi người dùng** (hook `guard` chặn `make data`). Nhà cung cấp trong `.env: SYNTH_LLM_PROVIDER` — kê khai trong hồ sơ, không ghi "tự làm chủ".
- Prompt template + tham số + mẫu đầu ra của mỗi bước sinh/judge lưu `docs/prompt-log/tools/<YYYY-MM-DD>-<bước>-<model>.md` (do script pipeline ghi; không sửa INDEX tay).
- Dữ liệu pilot thô (audio, ảnh app thật) không bao giờ vào repo/Drive/tập huấn luyện; chỉ số tổng hợp ẩn danh.

## Thư viện và cấu trúc
- Chỉ dùng thư viện trong `config/allowed-deps.yaml`; thêm mới → hỏi, ADR, thêm vào `data/pyproject.toml`.
- Mọi bước chạy được riêng lẻ (`uv run python -m ctcv_data.pipeline.<bước>`), idempotent, có `--limit` cho test; log JSON không PII qua `ctcv_core.logging`.
- Test: fixture tí hon có seed trong `data/tests/`; test schema đầu ra; test bộ lọc từ chối mẫu xấu (PII, 3 câu, thuật ngữ, drill có lời thoại).

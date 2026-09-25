---
name: hackathon-kit
description: Quy trình hackathon 2 ngày (vòng khu vực, 60 % điểm) và thử thách cải tiến 12 giờ (chung kết) của CTCV bằng plugin ctcv-kit — đọc đề ở hackathon/input, chọn 2 bài toán con chứng minh được bằng số, lịch giờ, mốc, /daily mỗi 4 giờ. Chỉ gọi tay bằng /hackathon-kit.
argument-hint: "[2-ngay | 12-gio | dien-tap]"
disable-model-invocation: true
---
# /hackathon-kit $ARGUMENTS (idea §13, prompt.md §6 `/hackathon`, `hackathon/README.md`, ADR-006 Pha B)

Đề và dataset BTC ở `hackathon/input/` (gitignore nếu BTC cấm phân phối). Bộ kit = `plugins/ctcv-kit` (sinh bằng `make plugin`; cài vào repo mới: `claude --plugin-dir plugins/ctcv-kit`) + các mô-đun tái dùng: ingestion (`data/src/ctcv_data/pipeline`), RAG có trích dẫn + `verify_citation`, agent planner + tool router + guardrail (thêm tool = 1 file Python có schema + `config/tools.yaml`), sandbox engine (máy trạng thái JSON), giọng nói (ASR/TTS), eval harness + red-team + k6, Docker Compose profile `cpu` + status page, template hồ sơ/slide/script demo. **Mặc định CPU-only** (laptop 3 người, Qwen3.5-2B GGUF, PhoWhisper-tiny); có máy chủ riêng → trỏ `VLLM_BASE_URL`.

## Chế độ `2-ngay` (giờ 0–48 theo idea §13; biến thể 2 × 10 giờ trong `hackathon/README.md` §3)
1. **Giờ 0–2**: `architect` đọc đề, khám phá dữ liệu (subagent chỉ đọc, EDA nhanh), đề xuất **2 bài toán con chứng minh được bằng số** kèm kế hoạch giờ; người dùng chọn. Mốc H2: bài toán chốt, ghi vào DAILY.
2. **Giờ 2–6**: ingestion + RAG có trích dẫn (hoặc baseline bảng) + **eval baseline** bằng kit. Mốc H6: bảng số baseline.
3. **Giờ 6–14**: tính năng lõi trên kit — `backend-dev` ∥ `frontend-dev` ∥ `data-engineer` (mỗi người thật sở hữu một mô-đun). Mốc H10/H14: **demo chạy end-to-end** (CPU), URL demo.
4. **Giờ 14–20**: `qa-tester` + `security-redteam` + deploy staging/status page.
5. **Giờ 20–34**: dữ liệu thật, kết quả, ablation, mục "kết quả chưa đạt".
6. **Giờ 34–40**: `docs-writer` slide + script demo 5 phút; `qa-tester` chạy lại; tập thuyết trình 2 lần.
7. **Giờ 40–48**: dự phòng, nộp. **Mỗi 4 giờ chạy `/daily`**; commit đều; prompt log tự ghi (nếu BTC yêu cầu nộp).
Giữ ba nguyên tắc bất biến; không thêm thư viện ngoài allow-list của kit mà không ghi lại; không mở rộng phạm vi sau H14.

## Chế độ `12-gio` (chung kết — nội dung BTC chưa công bố, chuẩn bị 3 hướng + dự phòng)
| Giờ | Việc |
| --- | --- |
| 0–1 | Đọc đề; chọn 1–2 cải tiến đo được; **đo trước** (p95, red-team, eval) bằng bộ đo có sẵn |
| 1–5 | Ưu tiên 1 — tối ưu hệ thống: batching vLLM, cache TTS, lượng tử hóa thấp hơn; kịch bản "giảm 30 % độ trễ" |
| 5–8 | Ưu tiên 2 — bảo mật: mở rộng red-team (200 → 250), checklist OWASP Agentic trước/sau, test hồi quy |
| 8–10 | Ưu tiên 3 — tích hợp tool/nguồn mới cho agent (< 1 giờ mỗi tool nhờ schema; đã tập ở diễn tập #2) |
| 10–11 | Dự phòng: nhóm người dùng/tính năng theo yêu cầu giám khảo → kịch bản sandbox JSON mới + UI |
| 11–12 | **Đo sau**, bảng trước/sau, slide 3 trang, tập phản biện |
Làm trên nhánh/máy riêng — không deploy lên bản đang chấm trong 48 giờ đóng băng; trực ca giữ nguyên.

## Chế độ `dien-tap` (Pha B: CN 4/10 đề dạng bảng 8 giờ; T5 8/10 đề văn bản 6 giờ)
Chạy từ đề đến demo bằng kit; đo giờ đạt mốc H6/H10; ghi chỗ tắc vào `docs/status/DAILY.md`; sửa kit ngay sau; mỗi thành viên giải thích được mô-đun mình phụ trách.

## Kết thúc
Tóm tắt ≤ 15 dòng: bài toán, mốc đạt/trễ, URL demo, bảng số (baseline → cuối), ablation, việc còn lại, rủi ro; phản biện dự kiến (idea §13) và câu trả lời có sẵn trong `docs/dossier/src/`.

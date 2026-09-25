# ADR-007 — Chuyển sang dự thi Data for Life 2026 (đề DA940-01) và phạm vi bản nộp 25/9/2026

Ngày: 2026-09-25 · Người quyết: người dùng (việc đổi cuộc thi đã quyết ngày 25/9; mục 1, 2, 5 chờ chốt) · Trạng thái: **đề xuất** · Liên quan: ADR-006 (thay phần tuyến và lịch BTC), E03, E05, brief §1/§3/§7, D11–D12; `docs/competition/DFL-2026-yeu-cau.md`; `docs/analysis/2026-09-25-nguon-du-lieu-tthc.md`; phụ lục `ADR-007-hop-dong.md`

## Bối cảnh
Ngày 25/9, người dùng bỏ cuộc thi Sáng tạo trẻ AI (Bảng C) và dự thi Data for Life mùa 4 do Bộ Công an tổ chức. Form nộp ghi hạn vòng 1 là **25/09/2026**. Hồ sơ gồm: phiếu đăng ký online; bản đề xuất tối đa 10 trang, PDF, tối đa 10 MB; video tối đa 3 phút; cam kết của mọi thành viên. Thể lệ cấm làm giả kết quả và cấm trình diễn tính năng không tồn tại (Điều 7, 13), và yêu cầu dữ liệu phải là nội dung cốt lõi.

Đề DA940-01 yêu cầu:
- N1: hướng dẫn quy trình, hồ sơ, phí.
- N2: điền biểu mẫu từ dữ liệu định danh.
- N3: trợ lý cho cán bộ tiếp nhận.
- K1: RAG trên kho TTHC.
- K2: mô hình nền tiếng Việt trong nước.
- K3: dẫn chiếu pháp lý và cảnh báo hiệu lực.
- K4: lớp chống ảo giác.
- K5: suy luận trong nước.

Ràng buộc hiện có: repo ở mức khung E01, chưa có kho tri thức; máy dev không có GPU; không được thêm thư viện hay đổi model. Cổng DVC quốc gia là SPA và robots cấm `/assets/`. Cổng DVC Bộ Công an render phía máy chủ, robots cho phép, và chân trang cho dùng lại nếu ghi nguồn.

## Lựa chọn
Chọn đề **DA940-01** (phương án B: BTL86-40). Bản nộp 25/9 là prototype chạy CPU, **trợ lý thủ tục hành chính có kiểm chứng**, và chỉ trình bày phần chạy thật.

1. **Nguồn sự thật về hồ sơ:** chuyển sang `DFL-2026-yeu-cau.md`. File BTC-2026 giữ làm lưu trữ; D11–D12 ngừng áp dụng. CLAUDE.md sửa đúng hai dòng tham chiếu, cần người dùng duyệt. Thư mục mới: `docs/dossier/dfl/` (bản dựng ở `docs/dossier/out/dfl/`, gitignore) và gói con `ctcv_agent/rag/`.
2. **Dữ liệu:**
   - ≥ 50 TTHC thật (mục tiêu khoảng 110) từ `dichvucong.bocongan.gov.vn`, một miền con đã có trong allowlist.
   - Tôn trọng robots, cách nhau ≥ 1,2 giây mỗi yêu cầu, manifest có sha256 của nội dung đã chuẩn hóa.
   - Registry `tthc-bca-v1`: `redistribute: false`; `tos_checked_on` do một thành viên xác nhận.
   - Bản ghi theo `config/schemas/tthc-record.schema.json`.
3. **Trả lời:**
   - Chỉ mục lai BM25 + BAAI/bge-m3, viết bằng Python thuần; Qdrant để sau.
   - `planner_small` viết đúng 1 câu từ đoạn nguồn: đầu ra JSON, không có tool, tắt thinking.
   - Lớp kiểm chứng: mọi con số phải có trong đoạn trích dẫn; độ phủ từ vựng đạt ngưỡng; chặn câu đòi OTP hay đòi làm thay.
   - Không đạt thì dùng câu mẫu tất định từ trường có cấu trúc. Không đủ căn cứ thì trả "cháu chưa chắc" và escalate.
   - Mọi ngưỡng đặt trong `config/rag.yaml`.
4. **Model:** không sửa `models.yaml`. `config/rag.yaml` khai `serving_aliases` (bge-m3 ↔ BAAI/bge-m3; qwen3.5:2b ↔ Qwen/Qwen3.5-2B), có test khóa. Ollama (MIT, chạy cục bộ trên nền llama.cpp) là runtime của đường CPU, tương đương D29. K2 để vòng 2, xử lý bằng ADR riêng.
5. **API:**
   - `/v1/coach/ask` chạy thật; `AskOut` và `Citation` thêm trường tùy chọn, tương thích ngược.
   - Thêm route thứ 17 `POST /v1/coach/intake-check` cho volunteer và officer: tất định, không dùng LLM, không phải tool của agent.
   - `join` và `login` có chế độ demo, chỉ bật khi đặt `CTCV_DEMO_*`; tắt mặc định và bị cấm ở prod.
   - `test_contract.py`: chuyển ca 501 của `/coach/ask` sang test thật, vẫn giữ các kiểm 401/403.
6. **Tool:** không thêm tool, không sửa `tools.yaml`. `search_guides` và `verify_citation` chỉ thêm trường tùy chọn; `verify` kiểm thêm con số.
7. **Hoãn sang BACKLOG:** N2 (chạm bất biến 2; ADR riêng theo hướng có đồng ý, xử lý trong phiên, không lưu, demo bằng dữ liệu giả), giọng nói, reranker, Qdrant, `qa_logs`.
8. **Trung thực:** mọi con số trong hồ sơ và video lấy từ `eval/reports/latest.json`. Chưa có số thì ghi "chưa đo" hoặc "mục tiêu".

**Phương án loại:**
- Giữ Bảng C: người dùng đã loại.
- Render SPA của cổng quốc gia: robots cấm.
- qdrant-client, numpy, pypdf: không có trong `uv.lock`.
- Làm chatbot hỏi đáp thuần: VNeID đã có trợ lý AI.
- Dùng API LLM nước ngoài: trái chủ quyền dữ liệu.
- Tool `intake_check` cho planner: là điểm dừng, lại không cần.
- Sửa `served_by` trong `models.yaml`: là điểm dừng.

## Hệ quả
- **Được:** prototype chạy thật trên CPU trong nước, có số đo thật: recall@5, citation-support, tỷ lệ ảo giác khi có và không có lớp kiểm chứng, tỷ lệ từ chối đúng, p50/p95. Đáp ứng N1, K1, K4, K5 và một phần N3 (đối chiếu hồ sơ).
- **Mất:** chỉ phủ TTHC của Bộ Công an; chưa có ngày hiệu lực (hiện ngày truy cập thay thế); độ trễ trên CPU cao.
- **Phần bị chạm:** `config/rag.yaml` và 2 schema; prompt `tthc_ask.v1`; `tests/config`; agent (`rag/`, `ask`, `compose`, `intake`, `numeric`, `verify`, 3 file tool); api (schemas, coach, auth, settings, knowledge); data (crawl, normalize, chunk_embed, build_eval_sets); eval qa; web. Yêu cầu coverage ≥ 80 % và chạy lại red-team.
- **ADR-006:** phần tuyến và lịch BTC hết hiệu lực. Lịch vòng 2 DFL và 3 bản sửa cổng audit sẽ ghi ở ADR-008.

## Trạng thái
2026-09-25: đề xuất (architect). Người dùng đã quyết đổi cuộc thi; mục 1, 2, 5 chờ chốt. Xem lại khi Ban Tổ chức công bố mẫu đề xuất hoặc gia hạn, khi có kết quả vòng 1, hoặc khi suite qa chạm ngưỡng chặn.

## Đính chính (25/9/2026, sau lượt đo v1)
- "Máy dev không có GPU" (Bối cảnh), "prototype chạy CPU" (Lựa chọn), "chạy thật trên CPU", "độ trễ trên CPU cao" (Hệ quả) là giả định lúc lập ADR, **sai với máy đo thật**: laptop i5-12450HX, 12 luồng, RAM 15,7 GB, GPU rời NVIDIA RTX 4050 Laptop; Ollama tự nạp bge-m3 và qwen3.5:2b lên GPU (`eval/reports/env-tthc.json`, `ollama.loaded_at_end_of_run`). Mọi số độ trễ trong hồ sơ là **có GPU**; chưa có số đo chỉ-CPU.
- Mục 4: bản `qwen3.5:2b` Ollama phục vụ là lượng tử **Q8_0** (`env-tthc.json`), không phải GGUF Q4_K_M như `config/models.yaml` ghi cho `planner_small`. Hồ sơ kê khai Q8_0; sửa `models.yaml` là điểm dừng của người dùng.
- Trạng thái vẫn **đề xuất** cho tới khi người dùng chốt mục 1, 2, 5.

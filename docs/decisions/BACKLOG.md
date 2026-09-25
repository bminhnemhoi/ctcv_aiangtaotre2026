# BACKLOG — Ý tưởng và việc ngoài phạm vi E01 / bản nộp (không tự làm; đề xuất ở đây)

Quy tắc: orchestrator ghi vào đây thay vì tự mở rộng phạm vi (prompt.md §4); mỗi dòng có nguồn (phát hiện id / D-số / epic) và điều kiện mở lại. Người dùng quyết khi nào lấy ra thành epic/ADR.

## A. Cắt phạm vi theo ADR-006 (đề xuất, chờ chốt) — có thể mở lại ở Pha D hoặc sau cuộc thi
- [ ] **APK Android offline** (Qwen3.5-2B GGUF + PhoWhisper-tiny + ONNX) — thay bằng PWA offline (F09, C02-gap, D30). Điều kiện: Android SDK/NDK, llama.cpp hỗ trợ Qwen3.5, sau chung kết. `apps/android/README.md` chỉ ghi hướng phát triển.
- [ ] **Kèm cặp trên app thật** (OCR PaddleOCR/RapidOCR Apache + YOLOX-Tiny + tập ảnh có đồng thuận) — bản nộp chỉ ảnh sandbox (F08, N06, SEC-05). Điều kiện: bộ eval `pii-redaction` recall ≥ 0,99, phiếu đồng thuận riêng, ADR mới, thêm OCR vào `config/allowed-deps.yaml`.
- [ ] **Huấn luyện YOLOX-Tiny** trên 20.000 ảnh render + mAP50 ≥ 0,85 (E08 gốc) — hoãn; render chỉ ~3.000 ảnh để eval VLM (F08, F13).
- [ ] **ASR LoRA** trên 5–10 giờ giọng pilot có đồng thuận (idea §6 "tùy chọn") — bỏ ở v1.0/v2.0 (C05, F13); chỉ khi WER giọng địa phương kém giọng chuẩn > 6 điểm (idea §9) và có audio đồng thuận.
- [ ] **DPO** nếu E07 thiếu thời gian (giữ SFT) — plan §2 quy tắc cắt; quyết ở Pha D.
- [ ] **Kịch bản mức 2–3 cho cả 12 luồng** trước pilot tầng 2 — nếu E06 không kịp, ưu tiên mức 1 × 12 + mức 2–3 × 4 (E06 câu hỏi mở 2).
- [ ] **Prometheus + Grafana** — giữ Uptime Kuma + `/metrics` vLLM + script p95 từ log JSON (F13); mở lại cho thử thách 12 giờ "tối ưu hệ thống" nếu còn thời gian.
- [ ] **MinIO → Redis SETEX 60 s** cho ảnh (F13 đề xuất) — brief §2 giữ MinIO; xem lại nếu MinIO làm phình image/độ phức tạp.
- [ ] **testcontainers** cho integration (D15 giữ) — nếu quá chậm trên máy dev, dùng compose test (F13).
- [ ] **restore-drill hằng tuần** → chỉ trước T-72h (F13); Lighthouse ≥ 90 → "báo cáo"; 3 mock bố cục (prompt.md D3) → 1 mock.
- [ ] **Load test 50 người + p95 < 2,5 s đầu-cuối** (DoD #4) — thay bằng mục tiêu theo đường (F05); bản đầy đủ ở E11 Pha D.
- [ ] **Tập eval đầy đủ** (500 hội thoại, 1.500 + 200 ảnh, 10 giờ audio, 200 red-team, 100 mẫu người chấm) — bản nộp dùng cỡ cắt theo F13; mở rộng trước chung kết.

## B. Ngoài phạm vi plan §2 / ý tưởng giai đoạn sau (idea §10)
- [ ] **Zalo Mini App** làm kênh phân phối (idea §4, §10); trước mắt QR mở Chrome + màn "Mở bằng Chrome" (N04); Zalo bị bỏ khỏi pilot (ETH-12).
- [ ] **Tiếng Khmer, H'Mông** cho vắc-xin lừa đảo (idea §10, lộ trình 6 tháng); plan §2 ghi "tiếng dân tộc" ngoài phạm vi.
- [ ] **Kết nối thống kê với nền tảng số của Đoàn** (idea §10).
- [ ] **iOS native, tích hợp API thật VNeID/DVC/eTax/ngân hàng, nhận diện deepfake, thanh toán thật, tài khoản mạng xã hội** — plan §2 "ngoài phạm vi", giữ để trả lời phản biện.
- [ ] **MCP `postgres` read-only** cho Claude Code (prompt.md §3 nhắc, không có trong `.mcp.json` — CC-12/SEC-13/D24): chỉ thêm khi cần truy vấn dữ liệu pilot ẩn danh; qua ADR.
- [ ] **Agent teams** (prompt.md §2 quy tắc 6, "review kiến trúc đa góc nhìn ở E01/E05, điều tra sự cố, ngày hackathon") — E01 không dùng; cân nhắc ở E05 và tuần đóng băng nếu CLI hỗ trợ ổn định.
- [ ] **`/effort ultracode`, `/subtask`** — chỉ khi `claude --version` ≥ 2.1.203 (CC-05); ghi phiên bản vào DAILY.md.
- [ ] **Hook cứng đếm subagent** (PreToolUse `Task|Agent`, `.cache/subagents.json`, exit 2 khi ≥ 6) — CC-04; hiện chỉ là luật trong CLAUDE.md.
- [ ] **CI kiểm sha256 của `.claude/hooks/*` so với `docs/status/hooks.lock`** (N11) — sau khi hook ổn định.
- [ ] **Target mới `registry-check`** (chưa có trong Makefile) đối chiếu giấy phép registry với model card Hugging Face và fail CI nếu lệch (CF-06, C05).
- [ ] **Cổng `eval-threshold`** trong CI: PR chạm `config/eval.yaml` phải có label (CC-08) — sau khi có GitHub Pro.
- [ ] **Bản đồ năng lực số theo thôn/tổ** (E10 đủ) — nếu không kịp Pha D, để sau chung kết.
- [ ] **Gói "lớp Bình dân học vụ số 2.0"** cho một phường (idea §10) — tài liệu triển khai sau cuộc thi.

## C. Phát hiện mức "minor" từ rà soát 18/9 (mỗi dòng = một việc backlog; xử lý khi chạm epic liên quan)
- [ ] **CF-06** Kê khai: target `registry-check` (mục B, chưa có), bản kê khai nêu rõ API thương mại chỉ ở bước sinh dữ liệu, Claude Code ở bước viết mã — DOSSIER.
- [ ] **CF-07** URL sống liên tục 2 tầng (VPS CPU luôn bật + GPU theo lịch), status page hiện chế độ — E12; thêm vào DoD "URL công khai sống từ ngày nộp đến chung kết".
- [ ] **C04** Sửa "YOLO" → "YOLOX-Tiny (Apache-2.0)" ở 14 chỗ idea.md — chỉ errata (D31); CLAUDE.md có câu cấm ultralytics/AGPL.
- [ ] **C05** idea §6 "tự fine-tune 3 mô hình" → thực tế 2 (huấn luyện viên; detector hoãn) + ASR LoRA tùy chọn — errata + hồ sơ trung thực.
- [ ] **C09** "12 epic" → 14 (E01–E12 + PILOT + DOSSIER); argument-hint `/epic [E01..E12|PILOT|DOSSIER]` — gói A.
- [ ] **F02** Ablation "9B vs 2B tại chỗ" chỉ khi 2B cũng được train cùng dữ liệu, hoặc ghi "2B base" — E07.
- [ ] **SEC-03** Đã đặc tả trong ADR-004; còn lại: judge nhỏ lọc câu mệnh lệnh trong chunk RAG (hiện regex) — E05/E11.
- [ ] **LIC-07** Thêm file `NOTICE` với điều khoản BSD của PhoWhisper; `pip-licenses` + `license-checker` (npm) trong `make audit` — gói F/I.
- [ ] **LIC-08** `eval/sets/audio` chỉ manifest + script tải lại; báo cáo WER tách theo nguồn; TTS NC phải kê khai — E04.
- [ ] **LIC-10** `sources.yaml` có `source_type`, `tos_checked`; trang ngân hàng chỉ khi ToS cho phép; UI trích ≤ 2 câu — E03.
- [ ] **ETH-12** Bỏ Zalo khỏi pilot; `contact_zalo` nullable chỉ nếu người dùng muốn (kèm `contact_consent_at`); ASR in-memory có test; GPU trong nước — PILOT/E12.
- [ ] **CC-04** Xóa 2 biến env không tồn tại (đã làm D3); hook đếm subagent (mục B).
- [ ] **CC-05** `effortLevel: xhigh` trong settings (D17); ghi chú `claude update` — gói A.
- [ ] **CC-09** architect read-only trả nội dung ADR, docs-writer ghi (D19); security-redteam ghi chỉ `eval/redteam/**`, `docs/security/**` — gói A.
- [ ] **CC-12** `.mcp.json` chỉ playwright, `gh` CLI thay MCP GitHub, xóa `mcp.json` rỗng (D24) — gói A.
- [ ] **CC-13** Plugin ở `plugins/ctcv-kit/` sinh bằng `make plugin`; thêm bước `claude plugin validate plugins/ctcv-kit` vào `make plugin` (target riêng `kit-validate` chưa có trong Makefile) — gói A/Pha B.
- [ ] **S11** Pha C cổng quyết định 12–18/10; hỏi BTC về cập nhật hồ sơ và URL xác minh trước 20/10 — ADR-006.
- [ ] **N12** docs-check chỉ kiểm INDEX hợp lệ + hash khớp; "phiên đã có log" chuyển sang SessionEnd/checklist PR (D20).
- [ ] **N13** PostToolUse chỉ `ruff format` + prettier, không `--fix`/pytest (D23).
- [ ] **N14** `docs/prompt-log/tools/` cho prompt sinh dữ liệu/judge; `docs/prompt-log/pre-D1/` cho phiên soạn 3 tài liệu; README Drive giải thích tầng system prompt — DOSSIER.
- [ ] **N15** Định nghĩa lại tag v1.0/v1.5/v2.0 = bản được nộp — ADR-006.
- [ ] **N16** Lead time: giấy xác nhận SV 3–7 ngày, domain `.vn` 1–3 ngày, GPU quota, GitHub Pro — việc người dùng ngày 18/9.
- [ ] **CF-08** Script 2 video viết cho bản có thật ngày nộp; không nhắc tính năng chưa có — DOSSIER.
- [ ] **CF-09** Nội dung thử thách 12 giờ chưa được BTC công bố; `/hackathon` giữ 3 ưu tiên nhưng chuẩn bị cả kịch bản "thêm nhóm người dùng/tính năng theo yêu cầu giám khảo" — hackathon/README.
- [ ] **CF-10** Mục 7–9 ở ngày nộp dùng bằng chứng thay thế; `make dossier` không đỏ vì thiếu pilot 30/ablation fine-tune (placeholder có nhãn "sơ bộ") — DOSSIER.
- [ ] **C14** Thống nhất số đếm: 16 route (brief §3), 7 prompt P0–P6 (plan) → thay bằng prompt.md, "3/6 thành phần cần người" (2 video + giấy xác nhận), danh sách target Makefile duy nhất = brief §10 — CLAUDE.md/README.
- [ ] **C15** Cấu hình Claude Code khớp binary 2.1.119 (D17, D24); xóa `mcp.json` rỗng — gói A.
- [ ] **F14** Giấy phép kê khai đúng (BSD-3-Clause, YOLOX) — registry đã sửa; cấm `pip install ultralytics` bằng `make audit`.
- [ ] **SEC-13** Không MCP GitHub với PAT rộng; `gh` CLI với allow `Bash(gh *)`; `enabledMcpjsonServers: ["playwright"]` — gói A.
- [ ] **SEC-14** INDEX một dòng/session, hash cuối ở SessionEnd; commit `docs/prompt-log/` mỗi ngày để git history là bằng chứng toàn vẹn; Bash không được ghi vào `docs/prompt-log/**` (guard) — gói A/DOSSIER.
- [ ] **CC-15** Allow-list thêm `git merge`, `git push origin epic/*`, `gh`, `npx`, `python`, `ruff`, `prettier`; `disallowedTools` đúng cú pháp — gói A (D17–D24).
- [ ] **S12** Thiết kế pilot thống nhất: buổi 2 = +5 ngày, ôn ngày 2/5 bằng thẻ QR — PILOT/ADR-006.
- [ ] **S13** Domain `.vn` + Uptime Kuma xanh 24 giờ trước nộp → E12-lite phải xong trước 27/9 — ADR-006.

## D. Vòng 2 Data for Life 2026 (ADR-007, đề xuất 25/9) — làm sau khi nộp vòng 1
- [ ] **N2 điền biểu mẫu từ dữ liệu định danh** (DA940-01): cần ADR riêng vì chạm bất biến 2. Hướng đi: công dân đồng ý trước, xử lý trong phiên, không lưu; demo chỉ dùng dữ liệu giả. Điều kiện: người dùng duyệt ADR và có test bất biến 2 cho luồng này.
- [ ] **K2 đánh giá mô hình nền tiếng Việt trong nước** (DA940-01): so với `planner_small` trên cùng bộ `qa_tthc`. Đổi model là điểm dừng, cần ADR và giấy phép đã kiểm.
- [ ] **K3 cảnh báo hiệu lực văn bản** qua `docs/legal/refs.yaml` (chỉ dùng văn bản có `verified_on`). Hiện giao diện chỉ ghi "Lấy ngày …".
- [ ] **Mở rộng nguồn:** CSDL thủ tục hành chính quốc gia (gửi thư `docs/dossier/dfl/thu-de-nghi-du-lieu.md`) và cổng dịch vụ công cấp tỉnh. Mỗi nguồn mới vào `data/sources.yaml` theo quy trình E03, có robots và `tos_checked_on`.
- [ ] **Qdrant và reranker `BAAI/bge-reranker-v2-m3`** thay chỉ mục Python thuần. Cần thêm `qdrant-client` vào `config/allowed-deps.yaml` (điểm dừng).
- [ ] **ASR PhoWhisper** cho câu hỏi bằng giọng nói. Chỉ đưa vào hồ sơ và video khi đã chạy thật.
- [ ] **Ghi `qa_logs` dạng hash** (E10): không lưu nguyên văn câu hỏi, không PII.
- [ ] **Hàng đợi escalate thật** cho tình nguyện viên và cán bộ. Chưa có thì giao diện không được ghi "đã báo".
- [ ] **Rate limit cho `/v1/coach/ask`** (theo checklist bảo mật của CLAUDE.md).

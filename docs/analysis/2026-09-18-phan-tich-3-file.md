# Phân tích chuyên sâu ba tài liệu CTCV (idea.md, plan.md, prompt.md) đối chiếu với yêu cầu thật của BTC

Ngày: 2026-09-18 · Người đọc: đội CTCV (3 thành viên) · Phương pháp: đọc trọn ba file (1.626 dòng), đọc trang BTC (thể lệ Bảng C, hồ sơ, lộ trình, FAQ, mẫu hồ sơ MẪU 3), kiểm chứng dữ kiện kỹ thuật (Hugging Face, giấy phép, văn bản pháp luật, binary Claude Code đang cài), rồi chạy rà soát 6 lăng kính bằng 77 agent với kiểm chứng phản biện từng phát hiện. Danh sách đầy đủ 70 phát hiện + 21 khoảng trống: `2026-09-18-review-findings.md` (kèm JSON có bằng chứng dòng).

## 1. Kết luận trong 60 giây

1. **Ba tài liệu rất tốt về sản phẩm và quy trình** — 5 mô-đun rõ, ba nguyên tắc bất biến đúng trọng tâm chấm (an toàn, kiểm chứng đầu ra, đạo đức), kiến trúc CaMeL, pipeline dữ liệu tự động, cổng chất lượng, hồ sơ sinh từ repo. Nội dung lõi nhất quán giữa ba file.
2. **Nhưng lịch không khớp cuộc thi thật.** Với D1 = 18/9, plan đặt "nộp hồ sơ" ở D20–D21 (7–8/10). Thực tế: tuyến đội tự do phải nộp **đủ hồ sơ + 2 video + Prompt Log ngay khi đăng ký, hạn 20/9** (bất khả thi); tuyến trường: trường gửi danh sách **trước 30/9** sau vòng xét nội bộ. Hồ sơ sơ bộ chiếm **40% điểm khu vực**; 60% còn lại là **hackathon 2 ngày trên dataset BTC** (10–11/10, TP.HCM), không phải chấm sản phẩm CTCV. Sản phẩm hoàn chỉnh, pilot 30 người, fine-tune, 48 giờ ổn định chỉ được xác minh ở **chung kết 20–22/11**.
3. **Hồ sơ phải theo MẪU 3 với đúng 13 mục** (không phải dàn ý 10 khối trong idea §12), kèm khối thông tin từng thí sinh và mục 13 = **link Google Drive công khai** chứa prompt log + minh chứng. Mẫu đã tải về `docs/template/AI2026_Mau_ho_so.docx`.
4. **Bốn lỗi sự kiện cần sửa trước khi vào hồ sơ:** Qwen3.5-1.7B không tồn tại (dải nhỏ là 0.8B/2B/4B/9B → dùng 2B); PhoWhisper là BSD-3-Clause (không phải Apache-2.0); "YOLO" phải là YOLOX-Tiny (Ultralytics là AGPL); Qwen3.5-9B đã đa phương thức nên Qwen3-VL-8B riêng là thừa trên GPU 24 GB. Đã ghi errata ở cuối ba file (không sửa thân văn bản).
5. **Bộ cấu hình Claude Code trong prompt.md chưa chạy được nguyên trạng** trên máy dev Windows: alias `fable` không hợp lệ với CLI 2.1.119 đang cài (→ `inherit`), hook bash+jq (→ Python), hook Stop kiểu agent chặn mọi lượt (→ bỏ), `qa-tester` background (→ bỏ), worktree cần commit đầu tiên, `mcp.json` sai tên. Tất cả đã được chốt lại trong `docs/decisions/E01-brief.md` v2 và dựng thành mã.

## 2. Việc người dùng phải làm hôm nay (Claude không làm thay được)

| # | Việc | Vì sao | Hạn |
| --- | --- | --- | --- |
| 1 | Gọi/email Đoàn trường + Phòng CTSV TDTU và BTC (Trung tâm PTKHCN&TNT): hạn nội bộ, hình thức xét, số suất, **ai upload 6 thành phần lên cổng và hạn nào**, có được cập nhật hồ sơ trước chung kết không, hackathon có được dùng AI/internet/máy chủ riêng không | Toàn bộ lịch treo vào câu trả lời này (N02) | 18–19/9 |
| 2 | Chốt đội hình: 3 người cùng trường, ≤ 22 tuổi, cam kết có mặt 10–11/10 (TP.HCM) và 20–22/11 (Hà Nội); thu lịch thi tháng 10–11 | Đội hình đóng băng sau đăng ký, không thay người (N08) | 18/9 |
| 3 | Nộp đơn xin giấy xác nhận sinh viên cho cả 3 | Lead time 3–7 ngày làm việc (N16) | 18/9 |
| 4 | Thuê GPU 24 GB (RTX 4090) và kiểm tra SSH + nvidia-smi; cân nhắc nhà cung cấp trong nước nếu giữ cam kết "máy chủ trong nước" | Điểm nghẽn đơn (S7, ETH-12) | trước 20/9 |
| 5 | GitHub: tạo repo `ctcv` (org hoặc Student Pack/Pro để bật branch protection), tạo commit đầu tiên | Worktree, CI, và lịch sử commit là minh chứng (CC-11) | 18–19/9 |
| 6 | Xuất các hội thoại đã dùng để soạn idea/plan/prompt (Claude.ai/Claude Code ngày 17/9) vào `docs/prompt-log/pre-D1/` | BTC yêu cầu Prompt Log "toàn bộ"; chuỗi minh chứng không được có khoảng trống (CF-03, N14) | 19/9 |
| 7 | Duyệt 5 quyết định ở mục 6 dưới đây (trả lời ngắn là đủ) | Điểm dừng bắt buộc theo plan §6 | 19/9 |

## 3. Đối chiếu yêu cầu BTC ↔ ba tài liệu

| Yêu cầu BTC (đã xác minh) | Ba tài liệu | Trạng thái sau hôm nay |
| --- | --- | --- |
| Tuyến tự do 20/9 nộp đủ; tuyến trường 30/9 | Coi 20/9 là lựa chọn mở; nộp ở D20–D21 | Errata + ADR-006 (lịch 3 pha, chờ chốt) |
| PDF ≤ 20 trang theo MẪU 3, 13 mục | Dàn ý 10 khối theo trang | `docs/dossier/src/01…13` đúng tên mục; build script điền mẫu |
| 2 video ≤ 5 phút | Có kịch bản nhưng viết cho bản v1.0 D21 | Kịch bản chuyển sang "bản 30/9" trong `docs/dossier/video/` |
| Giấy xác nhận SV cho tất cả thành viên | Có | Việc người dùng |
| Link repo hoặc mã | Có (public khi nộp) | README chạy 1 lệnh, LICENSE, SECURITY |
| Bản kê khai AI/dữ liệu/API/thư viện/phần tự xây | Sinh từ registry | `make declaration`; registry có giấy phép SPDX + `license_url`; allow-list `config/allowed-deps.yaml` |
| Prompt Log gồm System Prompt + toàn bộ hội thoại, trên Google Drive (mục 13) | ZIP có hash; hook bash copy transcript mỗi lượt | Hook Python 1 file/phiên + snapshot "system prompt" + subagent transcript + redaction trước khi lên Drive |
| Khu vực = hackathon 2 ngày dataset BTC (60%) | Bộ kit RAG/agent, 1 buổi diễn tập không ngày | ADR-006 Pha B (1–9/10): kit + đường EDA/bảng + 2 diễn tập; skill `/hackathon` |
| Chung kết: 12 giờ cải tiến, 48 giờ ổn định | Có (plan §8) | Giữ; Pha D |
| Tiêu chí: giá trị thực tiễn, phương pháp, dữ liệu, làm chủ mô hình, kết quả, kiểm chứng đầu ra, bảo mật, đạo đức, triển khai | Bám sát (idea §1) | Giữ; hồ sơ 13 mục ánh xạ ở `docs/competition/BTC-2026-yeu-cau.md` §6 |

## 4. Đánh giá từng tài liệu

### 4.1 idea.md — bản mô tả ý tưởng (470 dòng)

**Mạnh:** bài toán có số liệu và nguồn; personas cụ thể; 5 mô-đun với đầu ra đo được; sandbox máy trạng thái JSON là lựa chọn kiến trúc đúng (nhanh, tất định, không đọc ảnh); tầng bảo mật theo CaMeL/OWASP Agentic; mục "kết quả chưa đạt" bắt buộc; phân tích rủi ro lạm dụng drill.

**Cần sửa (đã ghi errata):** 1.7B → 2B; PhoWhisper BSD-3; YOLO → YOLOX-Tiny; dàn ý PDF → 13 mục; tuyến 20/9 loại; 3 văn bản pháp luật chưa xác minh (TT 05/2026/TT-BKHCN, Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP) — Luật 134/2025/QH15 và NĐ 142/2026/NĐ-CP đã xác minh.

**Đề xuất (chờ quyết):** (a) một model Qwen3.5-9B cho cả huấn luyện viên và đọc màn hình (F03); (b) APK offline → PWA offline (sandbox tất định, clip TTS sinh sẵn) (F09); (c) kèm cặp trên **app thật** → hướng phát triển; bản nộp chỉ kèm cặp trên ảnh sandbox — tránh OCR + ảnh nhạy cảm (N06, SEC-05); (d) mục tiêu độ trễ tách theo đường: bước sandbox p95 < 1 s (không gọi LLM trực tuyến), hỏi đáp/kèm cặp p95 < 4 s, tải = 50 phiên hoạt động với think-time (F05); (e) bộ WER: tự ghi 60–90 phút giọng 50+ ba miền có đồng thuận, Common Voice/VIVOS chỉ là "giọng chuẩn" (F07); (f) TTS: tiêu chí giấy phép MIT/Apache/BSD + RTF CPU < 0,3 → mặc định Piper vi, MOS mục tiêu 3,5 báo cáo trung thực (F06).

### 4.2 plan.md — kế hoạch triển khai (634 dòng)

**Mạnh:** DoD toàn dự án có lệnh kiểm tra; hợp đồng API 14 endpoint + 9 bảng + 8 tool đủ chặt để nhiều agent viết mã nhất quán; runbook data/train/eval/deploy/pilot/hồ sơ; cổng chất lượng theo tầng; điểm dừng bắt buộc; ADR.

**Cần sửa:** lịch D1–D21 (blocker) → ADR-006; `make check` gộp eval/red-team cần model vào cổng PR trên CI không GPU → tách `check` (tất định) và `gate` (GPU); `make doctor` đòi GPU trên máy dev → `doctor` (dev) và `doctor GPU=1` (SSH); prompt log `.md`+E0X vs `.jsonl`+sha (mâu thuẫn với prompt.md) → 1 file/phiên theo `session_id`; hai bộ prompt E01 (P0 vs Master Prompt) → prompt.md thắng, §12 được thay thế; cây thư mục 3 nơi khác nhau → brief §1 là duy nhất; E02 "4 kịch bản" vs `make data` "12 × 3" vs E10 "8 kịch bản mới" → E02 viết tay 4, pipeline sinh 36 file, E10 làm UI; ngưỡng ảnh 90/80 và pilot buổi 2 = +5 ngày; drills schema thiếu trường nội dung → thêm `utterance` 1 lượt ≤ 40 từ có nhãn "[Mô phỏng]"; schema DB: `events.payload_json` cần allowlist, `display_name` = mã/biệt danh, `qr_token` có hạn; fine-tune bf16 seq 4k trên 24 GB sẽ OOM → QLoRA/seq 2k/GPU thuê riêng đêm; crawl SPA/WAF (dichvucong, vneid) cần Playwright/PDF và 50–150 URL duyệt tay thay vì "≥ 1.500 trang".

### 4.3 prompt.md — bộ prompt và cấu hình Claude Code (522 dòng)

**Mạnh:** chia 3 tầng (cấu hình repo / điều phối / quy trình) đúng; 10 subagent với ranh giới đọc/ghi; skill `/epic` gói trọn vòng lặp; anti-pattern list rất thực tế; hook là "luật cứng" — tư duy đúng.

**Cần sửa (đã dựng đúng trong `.claude/`):** `model: fable` → `inherit` (CLI 2.1.119 không có alias); bỏ `CLAUDE_CODE_MAX_*`; `effortLevel` (không phải `effort`) trong settings; `/effort ultracode` và `/subtask` cần `claude update`; hook bash+jq → Python stdlib, fail-closed, gọi qua `$CLAUDE_PROJECT_DIR`; hook Stop kiểu agent → bỏ (chặn cả plan mode, không xét `stop_hook_active`); `qa-tester` background → bỏ; `architect` permissionMode plan thì không tự ghi ADR → trả nội dung, docs-writer ghi; `reviewer` bỏ Bash; protect-paths bảo vệ cả `.claude/**`, `CLAUDE.md`, workflows, Makefile (marker `.claude/BOOTSTRAP` trong E01); guard chặn `--no-verify`, `docker compose config`, `printenv`, mọi biến thể đọc `.env`; PostToolUse format không `--fix`/không pytest; `.mcp.json` chỉ playwright (`cmd /c npx` trên Windows), GitHub qua `gh`; plugin đặt ở `plugins/ctcv-kit/` sinh bằng `make plugin`.

## 5. Lịch đề xuất (ADR-006, chờ chốt)

| Pha | Ngày | Bàn giao | Cổng |
| --- | --- | --- | --- |
| A — Hồ sơ sơ bộ | 18/9–29/9 | E01 (hôm nay) → E02 (4 kịch bản) → E03-lite (50–150 URL duyệt tay, RAG có trích dẫn) ∥ E04 (giọng nói, cần staging HTTPS) → E05 (base + guardrail + trích dẫn) → E09-lite (10 drill) → E10-lite (dashboard lớp) → staging công khai + status page → thử nghiệm sơ bộ n = 5–10 (26–27/9) → 2 video (26–28/9) → PDF 13 mục, kê khai, Prompt Log Drive (28–29/9) | Rà phạm vi 22/9 và 25/9 |
| B — Vòng khu vực | 1/10–9/10 | Tách plugin `ctcv-kit` + đường EDA/bảng/geospatial/dashboard CPU-only; diễn tập 4/10 (đề dạng bảng) và 8/10 (đề dạng văn bản); 3 người mỗi người một nhánh | Demo chạy ở giờ 10 của diễn tập |
| C — Cổng quyết định | 12/10–18/10 | Kết quả khu vực; hỏi BTC về cập nhật hồ sơ | Vào chung kết mới mở Pha D |
| D — Chung kết | 19/10–17/11 | E06 → E07 (QLoRA, GPU thuê đêm) → E08 (VLM grounding, ảnh sandbox) → E10 đủ 12 → E11 đủ 200 red-team + load → E12 prod + máy dự phòng → pilot 30 người 2 buổi (27/10–9/11, buổi 2 = +5 ngày) → hồ sơ cập nhật | Freeze 17–19/11, trực 3 ca |

Cắt phạm vi cho bản 30/9 (đề xuất): APK offline, YOLOX, kèm cặp app thật, DPO, LoRA giọng, kịch bản 5–12, Prometheus/Grafana (giữ Uptime Kuma), MinIO (Redis TTL), testcontainers (compose test).

## 6. Năm quyết định chờ người dùng (điểm dừng bắt buộc)

1. **Tuyến trường TDTU** và lịch 3 pha ở mục 5 — đồng ý?
2. **Một model** Qwen3.5-9B (planner + VLM, multi-LoRA) thay vì thêm Qwen3-VL-8B — đồng ý chạy spike 2 giờ rồi chốt?
3. **APK offline → PWA offline** cho bản nộp; APK vào "hướng phát triển" — đồng ý?
4. **Kèm cặp chỉ trên ảnh sandbox** cho bản nộp; app thật vào "hướng phát triển" — đồng ý?
5. **Pilot hai tầng** (n = 5–10 trước 29/9; 30 người 27/10–9/11) và DoD #7 chuyển sang bản chung kết — đồng ý?

Ngoài ra: ngưỡng `escalate_confidence` 0,6 hay 0,7 (E05); TTS mặc định Piper vi; nhà cung cấp GPU (trong nước hay không).

## 7. Trạng thái repo và hồ sơ (cập nhật 19/9/2026)

**Đã dựng (E01):** uv workspace 10 gói + `libs/core`; `config/` có schema; `.claude/` (12 hook Python, 11 agent, 16 skill, settings theo brief v2); 14 epic, ADR-001…006, `docs/legal/refs.yaml`; `services/api` (16 route, 9 bảng, Alembic), `services/agent` (8 tool whitelist, guardrail, quarantine schema kín, 4 test bất biến), `sandbox`, `drills`, `services/speech|vision`, `apps/web` (PWA chữ to), `data`, `training`, `deploy` (Compose cpu/gpu, CI check/gate/release), `eval` (harness, red-team 50 kịch bản + ablation). Số đo 19/9: 1.426/1.427 test, coverage lõi 99,4 %, web 33/33, red-team 0/50 rò rỉ, ablation tắt guardrail 45/50 đòn thành công.

**Còn dở vì chạm hạn mức (tiếp tục sau 24/9):** tích hợp E01 (`make check` chưa xanh do `config/allowed-deps.yaml` chưa chứa các gói mới), phần còn lại của gói `eval` (k6, pilot, tests), verify gói deploy/CI, sinh plugin `ctcv-kit`, hội đồng review + gia cố; sau đó E02 → E05 theo ADR-006.

**Hồ sơ giấy:** `docs/dossier/out/01_TaiLieuDuAn_CTCV.pdf` 16 trang theo MẪU 3 (số liệu tự động, "chưa đo" ghi đúng là chưa đo), `06_KeKhaiAI.pdf`, `07_PromptLog.zip`; hướng dẫn hoàn tất: `docs/dossier/HUONG-DAN-NOP.md`.

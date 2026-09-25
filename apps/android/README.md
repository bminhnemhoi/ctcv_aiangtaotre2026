# apps/android — bản Android chạy không mạng (hướng phát triển, E12)

**Trạng thái: chưa có mã.** Theo ADR-006 (đề xuất, chờ người dùng chốt) và phát hiện F09, bản nộp v1.0/v2.0 **không build APK**; lớp học mất mạng dùng **PWA offline** trong `apps/web` (service worker cache kịch bản JSON, câu huấn luyện viên sinh sẵn, clip TTS). Thư mục này chỉ ghi kế hoạch để hồ sơ (mục "hướng phát triển") và E12 tham chiếu; mọi thay đổi trạng thái đi qua `docs/decisions/BACKLOG.md`.

## Mục tiêu khi mở lại

Một APK cài từ file (không cần kho ứng dụng), chạy **6 kịch bản sandbox mức 1** hoàn toàn tại chỗ trên điện thoại Android tầm trung (≥ 4 GB RAM, Android 10+), giữ nguyên nguyên tắc giao diện của PWA (chữ ≥ 20 pt, một hành động mỗi màn hình, "Nói lại" và "Gọi tình nguyện viên" luôn hiện, nhãn "Ứng dụng mô phỏng").

## Mô hình chạy tại chỗ (khớp `config/models.yaml`)

| Vai trò | Model | Định dạng | Ghi chú |
| --- | --- | --- | --- |
| Huấn luyện viên | `planner_small` = Qwen3.5-2B (D8: Qwen3.5 không có bản 1.7B) + LoRA đã gộp (E07) | GGUF Q4_K_M (~1,5 GB) | Chỉ trả lời theo trạng thái sandbox có cấu trúc; ≤ 2 câu; cùng prompt `coach.v1` |
| Nghe | `asr_small` = vinai/PhoWhisper-tiny (BSD-3-Clause, D10) | GGML/whisper.cpp hoặc ONNX INT8 | Xử lý trong bộ nhớ, không ghi file |
| Nhìn | `ui_detector` = YOLOX-Tiny (Apache-2.0, D7 — không Ultralytics) | ONNX (~20 MB) | Chỉ khi kèm cặp qua ảnh được mở lại trên app thật (BACKLOG) |
| Đọc | TTS theo ADR-002 (Piper vi_VN là ứng viên nhẹ nhất) | ONNX / clip sinh sẵn | Câu lặp dùng clip cache từ `services/speech` |

## Ứng viên binding Android (chưa chọn — quyết định qua ADR khi mở lại)

| Nhu cầu | Ứng viên | Giấy phép | Nhận xét |
| --- | --- | --- | --- |
| LLM GGUF | `llama.cpp` (JNI qua `llama-android` example trong repo chính; hoặc `llamacpp-kotlin`) | MIT | Cùng engine với đường CPU chính thức của server (D29) → một bộ prompt/eval |
| LLM GGUF (thay thế) | MLC LLM / MediaPipe LLM Inference | Apache-2.0 | Nhanh hơn trên GPU điện thoại nhưng cần chuyển đổi model riêng |
| ASR | `whisper.cpp` (JNI, example `whisper.android`) | MIT | PhoWhisper-tiny chuyển sang GGML; INT8 |
| ASR (thay thế) | ONNX Runtime Mobile + Whisper ONNX | MIT | Dùng chung runtime với YOLOX |
| Detector | ONNX Runtime Mobile (NNAPI/XNNPACK) | MIT | YOLOX-Tiny export sẵn từ E08 |
| Vỏ ứng dụng | Capacitor bọc PWA hiện có (ưu tiên: tái dùng `apps/web`) hoặc Kotlin + Jetpack Compose | MIT / Apache-2.0 | Capacitor giữ một mã nguồn giao diện; native chỉ cho phần model |

Mọi thư viện mới phải vào `config/allowed-deps.yaml` (D26) trước khi dùng; không AGPL/GPL/CC-NC.

## 6 kịch bản offline (mức 1, lấy từ `sandbox/scenarios/`)

1. `chuyen-khoan-qr` — chuyển khoản bằng quét mã QR
2. `dang-nhap-vneid` — đăng nhập VNeID mô phỏng
3. `xac-nhan-cu-tru` — nộp hồ sơ xác nhận cư trú
4. `ke-khai-doanh-thu` — kê khai doanh thu trên eTax mô phỏng
5. `kiem-tra-bien-dong-so-du` — kiểm tra biến động số dư
6. `cai-app-kho-chinh-thuc` — cài ứng dụng từ kho chính thức

Hỏi đáp có căn cứ, kèm cặp qua ảnh và vắc-xin lừa đảo có TTS hiện "cần mạng" (như PWA offline — F09).

## Tiêu chí nghiệm thu (khi mở lại)

- Tắt mạng: chơi trọn 6 kịch bản; độ trễ một lượt huấn luyện viên p95 < 4 s (idea §5) trên máy tham chiếu.
- WER PhoWhisper-tiny tại chỗ báo cáo theo lát cắt (không phải cổng chặn — F07).
- APK < 2,5 GB kể cả model; không gọi mạng khi ở chế độ offline (kiểm bằng proxy chặn).
- Không lưu audio/ảnh; log không PII (`ctcv_core.logging` tương đương trên Android).

## Điều kiện mở lại

Sau chung kết 20–22/11/2026, khi (a) PWA offline đã chạy ổn ở lớp mất mạng, (b) có ≥ 2 lớp không thể dùng trình duyệt Chrome, và (c) người dùng chốt ngân sách thời gian ≥ 3 ngày dev. Ghi tại `docs/decisions/BACKLOG.md`.

# 12. Hướng phát triển, hoàn thiện và khả năng ứng dụng trong thực tiễn

> Nội dung trình bày: Nêu định hướng hoàn thiện sản phẩm trong thời gian tới; khả năng triển khai, mở rộng, duy trì hoặc ứng dụng sản phẩm trong học tập, đời sống, sản xuất, quản lý, dịch vụ công, phát triển kinh tế - xã hội hoặc phục vụ cộng đồng.

## 12.1. Lộ trình hoàn thiện

| Giai đoạn | Thời gian | Nội dung |
| --- | --- | --- |
| Pha A — hồ sơ sơ bộ | 18/9–29/9/2026 | Khung repo (đã xong 19/9), sandbox 4–6 kịch bản, RAG có trích dẫn, giọng nói, agent + guardrail, 10 kịch bản lừa đảo, dashboard lớp, staging HTTPS + trang status, thử nghiệm sơ bộ 5–10 người, hai video, hồ sơ 13 mục |
| Pha B — vòng khu vực | 1/10–9/10 | Tách bộ kit (plugin `ctcv-kit` + repo mẫu hackathon), diễn tập 4/10 (đề dạng bảng, 8 giờ) và 7/10 (đề dạng văn bản, 6 giờ) |
| Pha C — cổng quyết định | 12–18/10 | Khởi động Pha D khi có kết quả vào chung kết; hỏi BTC về việc cập nhật hồ sơ |
| Pha D — bản chung kết | 19/10–17/11 | Dữ liệu tổng hợp đủ, fine-tune + ablation, VLM đọc ảnh sandbox, đủ 12 kịch bản, red-team 200, load test 50, prod + máy dự phòng, pilot 30 người (27/10–9/11), hồ sơ cập nhật; đóng băng 17–19/11 |

**Sau cuộc thi (6 tháng):** PWA/Android offline với mô hình nhỏ chạy tại chỗ cho lớp không có mạng; kèm cặp trên ảnh app thật khi đủ ba điều kiện (OCR mã nguồn mở che PII trước khi lưu, tập ảnh có đồng thuận, recall che PII ≥ 0,99); Zalo Mini App; vắc-xin lừa đảo tiếng Khmer và H'Mông; kết nối thống kê với nền tảng số của Đoàn; LoRA giọng vùng miền khi có audio đồng thuận.

## 12.2. Khả năng ứng dụng trong thực tiễn

Gói "lớp Bình dân học vụ số 2.0" cho một phường gồm một máy tính bảng dùng chung, mã QR và hai tình nguyện viên; máy chủ dùng chung toàn tỉnh nên chi phí biên gần bằng 0. Mã nguồn Apache-2.0, `docker compose up` một lệnh, kịch bản mới là file JSON không cần lập trình, kho hướng dẫn tự cập nhật hàng tuần — Tỉnh/Thành đoàn hoặc trung tâm học tập cộng đồng tự vận hành, không phụ thuộc đội. Dashboard theo thôn/tổ cho cán bộ Đoàn dữ liệu để bố trí đội hình; báo cáo phong trào chuyển từ "lượt hỗ trợ" sang "số người tự làm được".

## 12.3. Chiến lược vòng khu vực và chung kết

Vòng khu vực (60% điểm) là hackathon 2 ngày trên dataset và bài toán xã hội do BTC cung cấp, nên CTCV được đóng gói thành bộ kit tái dùng: ingestion CSV/Excel/PDF/HTML, EDA và baseline dạng bảng (pandas, scikit-learn/LightGBM), RAG có trích dẫn, agent + guardrail, sandbox engine, eval harness, deploy CPU-only với Qwen3.5-2B, sinh slide/hồ sơ; ba thành viên chia mô-đun, mốc "phải có demo chạy" ở giờ 10, hai buổi diễn tập trong 1–9/10. Cho thử thách cải tiến 12 giờ ở chung kết, đội có sẵn bộ đo độ trễ, bộ red-team mở rộng được và kiến trúc tool có schema để thêm tool mới dưới 1 giờ; sản phẩm vận hành 48 giờ với máy dự phòng và trang status công khai.

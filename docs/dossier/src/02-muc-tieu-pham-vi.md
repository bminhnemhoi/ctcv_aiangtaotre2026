# 2. Mục tiêu, phạm vi và đối tượng ứng dụng của sản phẩm

> Nội dung trình bày: Nêu mục tiêu chính của sản phẩm; phạm vi ứng dụng; nhóm người dùng, tổ chức, đơn vị hoặc lĩnh vực có thể sử dụng, thụ hưởng sản phẩm.

## 2.1. Mục tiêu chính

CTCV là trợ lý AI đồng hành phong trào Bình dân học vụ số: dạy và làm cùng người dân năm nhóm kỹ năng số thiết yếu (thiết bị cơ bản; định danh VNeID; dịch vụ công trực tuyến; thanh toán và thuế số; an toàn số) bằng giọng nói tiếng Việt trong sandbox mô phỏng, có trích dẫn, không thu dữ liệu định danh. Mục tiêu đo lường của bản chung kết (cách đo: mục 7; kết quả: mục 8):

| Mục tiêu (bản chung kết) | Chỉ tiêu |
| --- | --- |
| Tự hoàn thành tác vụ sandbox không cần gợi ý (lần 2), pilot 30 người | ≥ 70% |
| Phút tình nguyện viên hướng dẫn mỗi người so với lớp truyền thống | Giảm ≥ 50% |
| Tỷ lệ "sập bẫy" trước/sau vắc-xin lừa đảo | Giảm ≥ 40% |
| Rò rỉ OTP/mật khẩu, thao tác thay người dùng trong red-team | 0 |
| Câu trả lời có trích dẫn hợp lệ | ≥ 95% |
| Độ trễ p95: bước sandbox / hỏi đáp | < 1 s / < 4 s |

## 2.2. Phạm vi

- **Bản nộp sơ bộ (tuyến trường, trước 30/9/2026) — mục tiêu; trạng thái thực tế tại ngày lập hồ sơ ở mục 6.1 và 8:** sandbox ≥ 6 kịch bản; agent huấn luyện viên (mô hình mở tự host, prompt có cấu trúc, guardrail cứng); hỏi đáp có trích dẫn; giọng nói; vắc-xin lừa đảo 10 kịch bản; dashboard lớp cơ bản; URL công khai + trang status; eval nhỏ; thử nghiệm sơ bộ 5–10 người.
- **Bản chung kết (đóng băng 17–19/11/2026):** 12 kịch bản × 3 mức; planner fine-tune (LoRA SFT + DPO) kèm ablation; VLM kèm cặp trên ảnh sandbox; red-team 200; load test 50 người; máy dự phòng; pilot 30 người có nhóm đối chứng.
- **Ngoài phạm vi:** tích hợp API thật của VNeID, Cổng Dịch vụ công, eTax hay ngân hàng; thanh toán thật; iOS; tiếng dân tộc; deepfake. APK offline (thay bằng PWA offline) và kèm cặp trên ảnh app thật chuyển sang mục 12 sau rà soát khả thi; bản nộp chỉ kèm cặp trên ảnh sandbox.

## 2.3. Đối tượng ứng dụng

| Nhóm | Đại diện | Nhu cầu | CTCV đáp ứng |
| --- | --- | --- | --- |
| Người dân học kỹ năng | Cô Lan, 63, bán tạp hóa; chú Bảy, 58, nông dân miền Tây; bà Hương, 70, sống một mình | Kê khai doanh thu, chuyển khoản, định danh, dịch vụ công, nhận diện cuộc gọi "công an" giả | Sandbox chữ ≥ 20 pt, một hành động/màn hình, giọng nói mặc định, mô phỏng lừa đảo có giải thích |
| Tình nguyện viên | Minh, sinh viên dẫn lớp 25–30 người | Giáo trình chuẩn; biết ai cần kèm riêng | Lộ trình 5 kỹ năng × 3 mức, dashboard, gợi ý "3 người cần kèm hôm nay" |
| Cán bộ Đoàn xã/phường | Chị Thảo | Thôn/tổ nào yếu kỹ năng gì; báo cáo chỉ tiêu | Bản đồ năng lực số theo thôn/tổ, xuất báo cáo |

Đơn vị triển khai: Đoàn phường/xã, Tỉnh/Thành đoàn (một máy chủ dùng chung), Đoàn trường, trung tâm học tập cộng đồng.

**Phần đội tự xây:** ba thành viên cùng Trường Đại học Tôn Đức Thắng, mỗi người sở hữu một mô-đun (kiến trúc–agent–bảo mật; dữ liệu–sandbox–pilot; đánh giá–hồ sơ–vận hành); đội tự quyết thiết kế (ADR), kịch bản và sư phạm, bộ đánh giá, duyệt dữ liệu, dẫn pilot; mã viết với Claude Code do đội điều khiển, kê khai bằng Prompt Log (mục 13).

# 7. Chỉ số, phương pháp hoặc tiêu chí đánh giá kết quả

> Nội dung trình bày: Nêu các chỉ số, phương pháp hoặc tiêu chí được sử dụng để đánh giá hiệu quả của sản phẩm; có thể trình bày kết quả định lượng, kết quả định tính, phản hồi người dùng hoặc tiêu chí so sánh phù hợp.

Mọi chỉ số chạy bằng `make eval`; số đo với người thật là phần quyết định, bài đo tự động là phần chứng minh kỹ thuật. Bảng 4: bộ chỉ số bản chung kết; cột "bản nộp" là quy mô đo thật ở mục 8.

| Nhóm | Chỉ số | Cách đo | Mục tiêu | Bản nộp | So sánh cơ sở |
| --- | --- | --- | --- | --- | --- |
| Hiệu quả học | Tự hoàn thành tác vụ sandbox không cần gợi ý (lần 2); thời gian, số bước sai lần 1 → 2 | Log sandbox | ≥ 70%; giảm ≥ 40% | Sơ bộ 5–10 người | Nhóm học không dùng CTCV |
| Hiệu quả tình nguyện viên | Phút hướng dẫn/người/kỹ năng | Bấm giờ tại lớp | Giảm ≥ 50% | Pilot chính thức | Lớp truyền thống |
| Chống lừa đảo | Điểm dễ tổn thương 0–100 trước/sau vắc-xin | 10 tình huống chấm tự động | Giảm ≥ 40% | 10 kịch bản | Trước can thiệp |
| Tin cậy nội dung | Câu dữ kiện có trích dẫn được nguồn hỗ trợ; hallucination | LLM-judge (thang 5, giữ ≥ 4) hiệu chỉnh bằng 50 mẫu người; so khớp kho | ≥ 95%; ≤ 3% | 100 câu Q&A | Cùng mô hình gốc không RAG |
| Phong cách | ≤ 2 câu; có hành động cụ thể; xác nhận ý định lượt đầu | Rule trên hội thoại giữ lại | 100%; ≥ 98%; 100% | 100 hội thoại | Chatbot tổng quát |
| Truy xuất | Recall@5 | 100 câu hỏi có nhãn | ≥ 0,9 | 100 câu | BM25 đơn |
| Thị giác (Pha D) | Nhận diện màn hình sandbox | Ảnh render giữ lại | ≥ 90% | — | VLM không schema |
| Giọng nói | WER theo giọng Bắc/Trung/Nam và nhóm tuổi (**báo cáo theo lát cắt**, không phải cổng chặn); RTF, MOS TTS | Tập tự ghi + Common Voice; 10 người nghe | WER ≤ 12% chuẩn, ≤ 18% địa phương; RTF < 0,3; MOS ≥ 3,5 | 1 giờ audio; 20 câu | Whisper gốc |
| An toàn | Rò rỉ OTP/mật khẩu; thao tác thay người dùng; PII trong log | Red-team tự động: injection trực tiếp/gián tiếp, moi OTP, "làm giúp trên app thật", lạm dụng drill | 0 / 0 / 0 (200) | 50 → 100 | Mô hình gốc không guardrail |
| Hiệu năng | p95 bước sandbox; p95 hỏi đáp; âm thanh đầu tiên; tỷ lệ lỗi | k6, 50 phiên có think-time | < 1 s; < 4 s; < 1,5 s; < 1% | 10 người | — |
| Dùng được | SUS người cao tuổi; quay lại ngày 5 | Phiếu giấy chữ to; mã lớp trên thẻ ôn tập | ≥ 70; ≥ 50% | Sơ bộ | — |

**Phương pháp và nguyên tắc:**

- **Hai cổng chất lượng:** `make check` (tất định, không cần mô hình: lint, test, contract API, schema, bất biến, guardrail thuần, audit) mỗi PR; `make gate` (eval rút gọn với LLM-judge, red-team có mô hình, load test) trên máy GPU hằng đêm và trước tag. Ngưỡng chấp nhận/chặn trong `config/eval.yaml` chỉ đổi qua ADR.
- **Tái lập:** tập đánh giá cố định bằng seed và checksum; hồ sơ chỉ nhận số từ `eval/reports/` (báo cáo do lệnh đo sinh ra, không gõ tay); chỉ số chưa đo được in đúng là "chưa đo".
- **Thử nghiệm với người thật, hai tầng:** (1) sơ bộ 5–10 người 50+ ngày 26–27/9/2026, một buổi + ôn ngày 2, có phiếu đồng thuận, báo cáo đúng quy mô, không suy diễn thống kê; (2) pilot chính thức 30 người qua Đoàn phường/Đoàn trường TDTU, 27/10–9/11/2026, chia ngẫu nhiên nhóm A (tình nguyện viên + CTCV) và nhóm B (cách hiện tại), buổi 2 cách 5 ngày, ôn ngày 2 và 5; đo SUS, hoàn thành, thời gian, điểm vắc-xin, phỏng vấn 5 câu.
- **Trung thực:** không đưa số chưa đo; mục "Kết quả chưa đạt" là bắt buộc.

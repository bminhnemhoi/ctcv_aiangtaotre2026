# 9. So sánh với phương án hoặc mô hình cơ sở, phân tích đóng góp của các thành phần trong hệ thống (nếu có)

> Nội dung trình bày: So sánh sản phẩm với phương án, mô hình, công cụ hoặc cách làm tương tự, nếu có; nêu điểm mới, điểm cải tiến và vai trò đóng góp của các thành phần chính trong hệ thống.

## 9.1. So sánh với phương án cơ sở: chatbot tổng quát

Phương án cơ sở là cùng mô hình gốc Qwen3.5-9B dùng như chatbot thông thường (không sandbox, tool, RAG, guardrail, xác nhận ý định) — cách người dân đang "hỏi AI" hôm nay. Hàng "Thiết kế" đã hiện thực và kiểm thử ở khung sản phẩm; hàng số liệu đo trên bộ đánh giá của mục 7 trong Pha A, ô "chưa đo" là chưa có số thật.

| Tiêu chí | Chatbot tổng quát (cùng mô hình gốc) | CTCV (bản nộp) | Nguồn số |
| --- | --- | --- | --- |
| Thấy trạng thái màn hình của người học | Không | Có (trạng thái sandbox) | Thiết kế |
| Phong cách: ≤ 2 câu / hành động cụ thể / xác nhận ý định lượt đầu | {{eval:baseline.max_two_sentences|chưa đo}} / {{eval:baseline.has_concrete_action|chưa đo}} / {{eval:baseline.first_turn_intent_confirmation|chưa đo}} | {{eval:suites.dialogue.metrics.max_two_sentences|chưa đo}} / {{eval:suites.dialogue.metrics.has_concrete_action|chưa đo}} / {{eval:suites.dialogue.metrics.first_turn_intent_confirmation|chưa đo}} | 100 hội thoại |
| Câu dữ kiện có trích dẫn được nguồn hỗ trợ / hallucination | {{eval:baseline.citation_support|chưa đo}} / {{eval:baseline.hallucination|chưa đo}} | {{eval:suites.qa.metrics.citation_support|chưa đo}} / {{eval:suites.qa.metrics.hallucination|chưa đo}} | 100 câu Q&A |
| Rò rỉ OTP/mật khẩu / làm theo yêu cầu thao tác thật | {{eval:baseline.redteam_leaks|chưa đo}} / {{eval:baseline.redteam_real_actions|chưa đo}} | {{eval:engineering.redteam.leaks|0}} / {{eval:engineering.redteam.real_actions|0}} (guardrail, không mô hình) | {{eval:engineering.redteam.size|50}} kịch bản |
| Đo tiến bộ từng người học | Không | Có (bước, lần sai, gợi ý, thời gian) | Thiết kế |
| Dữ liệu rời máy chủ do đội vận hành | Có (API bên thứ ba) | Không | Thiết kế |

**Khác biệt với giải pháp hiện có:** trợ lý ảo của Đoàn (ai.ttnmedia.vn) phục vụ cán bộ tra cứu văn bản; "cổng trải nghiệm" của Cục Thuế chỉ mô phỏng kê khai thuế, không có huấn luyện viên và không đo tiến bộ; GuideMe (CHI 2026) hướng dẫn tại chỗ cho người cao tuổi (xác nhận ý định, highlight) nhưng không có sandbox tiếng Việt hay vắc-xin lừa đảo. CTCV không thay cổng chính thức nào mà là lớp học an toàn đứng trước chúng.

## 9.2. Đóng góp của các thành phần (ablation)

Ablation chia hai đợt: đợt 1 (bản nộp) tắt/bật từng thành phần trên **cùng mô hình gốc**, không cần fine-tune; đợt 2 (Pha D) so sánh các mức fine-tune và VLM.

| Cấu hình | Thay đổi | Chỉ số bị ảnh hưởng | Kết quả |
| --- | --- | --- | --- |
| Đầy đủ (bản nộp) | — | — | Bảng ở mục 8.1 |
| − RAG | Tắt tool tìm hướng dẫn và kiểm chứng trích dẫn | Citation-support, hallucination | {{eval:ablation.no_rag.citation_support|chưa đo}} / {{eval:ablation.no_rag.hallucination|chưa đo}} |
| − Guardrail (**đã đo**, không cần mô hình) | Planner nhận thẳng văn bản dán, bỏ quy tắc cứng, che PII và kiểm tra đầu ra; giữ whitelist tool | Số đòn tấn công thành công | **{{eval:engineering.redteam_no_guardrail.attacks_succeeded|chưa đo}} / {{eval:engineering.redteam_no_guardrail.size|50}}** (rò rỉ {{eval:engineering.redteam_no_guardrail.leaks|—}}, thao tác trái phép {{eval:engineering.redteam_no_guardrail.real_actions|—}}) so với **{{eval:engineering.redteam.leaks|0}} / {{eval:engineering.redteam.size|50}}** khi bật |
| − Xác nhận ý định | Bỏ ràng buộc lượt đầu | Số bước sai lần 1 trong sandbox | {{eval:ablation.no_intent.mistakes_delta|chưa đo}} |
| − Kiểm chứng trích dẫn | Trích dẫn top-1 không qua reranker | Citation-support | {{eval:ablation.no_verify.citation_support|chưa đo}} |
| Qwen3.5-2B (đường CPU) thay 9B | Đổi mô hình | Phong cách, hallucination, p95 | {{eval:ablation.small_model.summary|chưa đo}} |
| Đợt 2 (Pha D): mô hình gốc / SFT / SFT+DPO; VLM có/không JSON schema + grounding | Fine-tune; prompt VLM | Phong cách, hallucination; nhận diện màn hình | Kế hoạch — chưa có số |

**Phân tích:** ba thành phần tạo phần lớn giá trị và đều do đội tự thiết kế: (1) sandbox máy trạng thái cho huấn luyện viên "nhìn thấy" người học mà không cần đọc ảnh; (2) RAG có kiểm chứng trích dẫn quyết định độ tin cậy nội dung; (3) tầng guardrail CaMeL quyết định an toàn — phép đo trên cho thấy cùng bộ tấn công và cùng planner "tệ nhất", bỏ tầng này thì phần lớn đòn tấn công thành công. Fine-tune (đợt 2) được kỳ vọng tăng ổn định phong cách và giảm độ trễ, không phải điều kiện để sản phẩm hoạt động; nếu không thắng mô hình gốc, đội báo cáo trung thực và giữ mô hình gốc.

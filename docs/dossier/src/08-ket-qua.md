# 8. Kết quả thử nghiệm, phân tích ưu điểm, hạn chế và khả năng mở rộng

> Nội dung trình bày: Trình bày kết quả thử nghiệm sản phẩm; nêu ưu điểm, hạn chế trong quá trình thử nghiệm; đánh giá khả năng mở rộng, nâng cấp hoặc áp dụng sản phẩm trong phạm vi lớn hơn.

Mọi số trong mục này được đọc tự động từ `eval/reports/` khi xuất hồ sơ (số kỹ thuật đo ngày {{eval:engineering.date_vi|19/9/2026}}). Chỉ số nào chưa đo được ghi đúng là "chưa đo" kèm thời điểm dự kiến; hồ sơ không chứa số ước lượng.

## 8.1. Kết quả đã đo: kiểm chứng kỹ thuật (không cần mô hình, tái lập bằng lệnh make check)

| Hạng mục | Kết quả | Ngưỡng |
| --- | --- | --- |
| Kiểm thử tự động Python (đơn vị, hợp đồng, bất biến) | {{eval:engineering.python_tests.passed|—}} / {{eval:engineering.python_tests.total|—}} đạt; {{eval:engineering.python_tests.failed|—}} chưa đạt (mục 8.4) | 100% |
| Độ phủ mã lõi (agent, sandbox, api, drills, core) | {{eval:engineering.coverage.percent|—}} % | ≥ 80% |
| Red-team guardrail, {{eval:engineering.redteam.size|50}} kịch bản tiếng Việt thuộc 8 nhóm tấn công (mục 7, hàng "An toàn") | {{eval:engineering.redteam.passed|—}} / {{eval:engineering.redteam.size|50}} đạt; {{eval:engineering.redteam.leaks|—}} rò rỉ; {{eval:engineering.redteam.real_actions|—}} thao tác thay người dùng | 0 / 0 |
| Validator kịch bản sandbox và kịch bản lừa đảo | {{eval:engineering.sandbox.invalid_fixtures_rejected|26}} + {{eval:engineering.drills.invalid_fixtures_rejected|26}} kịch bản lỗi cố ý đều bị từ chối đúng mã lỗi | 100% |
| Hợp đồng API | {{eval:engineering.api.routes|16}} route `/v1` có test hợp đồng; 9 bảng dữ liệu không có cột định danh (test bất biến) | Đủ |
| Giao diện cho người cao tuổi | {{eval:engineering.web_tests.passed|—}} / {{eval:engineering.web_tests.total|—}} test: cỡ chữ ≥ 20 pt, vùng bấm ≥ 56 px, tương phản ≥ 7:1 cho mọi cặp màu | 100% |
| Bốn test bất biến | Whitelist tool; không PII trong fixture và schema; dữ kiện phải có trích dẫn; không chuỗi tự do từ nguồn không tin cậy vào planner | Đạt |

![Hình 2. Màn hình chính của PWA — ảnh thật của khung sản phẩm (390 × 844): nhãn "Ứng dụng mô phỏng", chữ to, một hành động chính, luôn có "Nói lại" và "Gọi tình nguyện viên"](figures/08-man-hinh-chinh.png)

## 8.2. Chỉ số cần mô hình và người thật

| Chỉ số | Kết quả | Mục tiêu | Thời điểm đo |
| --- | --- | --- | --- |
| Citation-support / hallucination (100 câu Q&A) | {{eval:suites.qa.metrics.citation_support|chưa đo}} / {{eval:suites.qa.metrics.hallucination|chưa đo}} | ≥ 95% / ≤ 3% | Pha A |
| Hội thoại ≤ 2 câu / có hành động / xác nhận ý định | {{eval:suites.dialogue.metrics.max_two_sentences|chưa đo}} / {{eval:suites.dialogue.metrics.has_concrete_action|chưa đo}} / {{eval:suites.dialogue.metrics.first_turn_intent_confirmation|chưa đo}} | 100 / ≥ 98 / 100% | Pha A |
| Red-team có mô hình (50 → 200 kịch bản) | {{eval:redteam_model.leaks|chưa đo}} | 0 rò rỉ | Pha A → D |
| WER giọng chuẩn / địa phương / người 50+ | {{eval:suites.audio.metrics.wer_standard|chưa đo}} / {{eval:suites.audio.metrics.wer_regional|chưa đo}} / {{eval:suites.audio.metrics.wer_elderly|chưa đo}} | ≤ 12% / ≤ 18% / báo cáo | Pha A |
| p95 bước sandbox / hỏi đáp; tỷ lệ lỗi dưới tải | {{eval:suites.loadtest.metrics.sandbox_p95_s|chưa đo}} / {{eval:suites.loadtest.metrics.coach_p95_s|chưa đo}}; {{eval:suites.loadtest.metrics.error_rate|chưa đo}} | < 1 s / < 4 s; < 1% | Pha A (10 người) → D (50) |
| Thử nghiệm sơ bộ 5–10 người 50+: tự hoàn thành lần 2, SUS, điểm dễ tổn thương trước → sau | {{eval:pilot.summary|chưa diễn ra}} | Báo cáo đúng quy mô, không suy diễn thống kê | 26–27/9/2026 |
| Pilot chính thức 30 người, có nhóm đối chứng | {{eval:pilot_full.summary|chưa diễn ra}} | ≥ 70% tự hoàn thành; SUS ≥ 70 | 27/10–9/11/2026 |

## 8.3. Ưu điểm ghi nhận

- Bước sandbox do máy trạng thái quyết định, không gọi LLM trực tuyến: câu huấn luyện viên luôn khớp màn hình, độ trễ không phụ thuộc GPU.
- An toàn được ép bằng cấu trúc, không bằng lời dặn: với planner bị thay bằng bản "lặp lại đòn tấn công", hệ thống chặn {{eval:engineering.redteam.passed|50}}/{{eval:engineering.redteam.size|50}} kịch bản; tắt guardrail thì {{eval:engineering.redteam_no_guardrail.attacks_succeeded|—}}/{{eval:engineering.redteam_no_guardrail.size|50}} đòn thành công (mục 9.2).
- Hành vi quan trọng có test tự động từ khung, nên mọi thay đổi mô hình và dữ liệu về sau đi qua cùng một cổng chất lượng.

## 8.4. Hạn chế và kết quả chưa đạt

1. **Chưa có số đo với mô hình và người thật** tại ngày lập hồ sơ (bảng 8.2); kết quả hiện có là kiểm chứng kỹ thuật của khung sản phẩm.
2. **Chưa fine-tune planner.** Bản nộp dự kiến chạy mô hình gốc Qwen3.5-9B với prompt có cấu trúc; bảng ablation base/SFT/SFT+DPO thuộc Pha D.
3. **Số kịch bản:** {{eval:engineering.sandbox.scenarios|1}}/12 kịch bản sandbox và {{eval:engineering.drills.scenarios|1}}/20 kịch bản lừa đảo (mỗi loại một kịch bản mẫu hoàn chỉnh qua validator).
4. **Test chưa đạt:** kiểm tra allow-list thư viện chưa được cập nhật sau khi các dịch vụ thêm gói phụ thuộc; hoàn tất ở bước tích hợp E01.
5. **Kèm cặp trên ảnh app thật, APK offline và YOLOX** không nằm trong bản nộp (mục 12); WER giọng địa phương dự kiến cao hơn giọng chuẩn, bù bằng nút "Nói lại" và bàn phím chữ to.

## 8.5. Khả năng mở rộng

Kịch bản mới là một file JSON qua validator, không cần lập trình; kho hướng dẫn cập nhật hàng tuần theo `sources.yaml`; mọi mô hình thay được qua `config/models.yaml`; Tỉnh đoàn tự host bằng `docker compose up`, ước tính dưới 20.000 đồng/1.000 lượt tương tác.

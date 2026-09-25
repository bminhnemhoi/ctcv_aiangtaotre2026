# 3. Dữ liệu sử dụng, nguồn dữ liệu và tính hợp lệ của dữ liệu

> Nội dung trình bày: Liệt kê các loại dữ liệu đã sử dụng; nêu rõ nguồn dữ liệu; hình thức thu thập dữ liệu; căn cứ bảo đảm dữ liệu có nguồn gốc rõ ràng, được phép sử dụng và phù hợp quy định về quyền riêng tư, bản quyền, dữ liệu cá nhân.

## 3.1. Các loại dữ liệu

CTCV không thu thập dữ liệu bằng tay, không dùng dữ liệu cá nhân của người dân để huấn luyện. Bảy tập dữ liệu do `make data` tạo hoặc tải về; mỗi tập có bản ghi trong `data/registry/datasets.yaml` (nguồn, giấy phép SPDX, ngày kiểm tra điều khoản, SHA-256, `pii: none`); Bản kê khai sinh từ registry này.

| Tập dữ liệu | Nguồn và cách thu thập | Quy mô nộp → chung kết | Cơ sở sử dụng | Dùng cho |
| --- | --- | --- | --- | --- |
| Kho hướng dẫn chính thống | Cổng Dịch vụ công quốc gia, VNeID/Bộ Công an, Cục Thuế (eTax Mobile), cảnh báo của Cục An toàn thông tin, Hiệp hội An ninh mạng, hướng dẫn của ngân hàng; 50–150 URL/PDF đội duyệt tay; crawler tôn trọng robots.txt (1 yêu cầu/giây), SPA render bằng Playwright, PDF trích bằng PyMuPDF | ≥ 300 chunk → 1.500 trang | Văn bản công khai; chỉ truy xuất, trích dẫn ≤ 2 câu kèm link; **không phân phối lại** | RAG, sinh kịch bản |
| Kịch bản sandbox | 4 kịch bản mức 1 đội viết tay; còn lại LLM sinh từ kho hướng dẫn theo JSON Schema → validator → người duyệt 30 mẫu/vòng | 6 → 12 kịch bản × 3 mức | Đội tự tạo, CC BY 4.0 | Sandbox |
| Hội thoại huấn luyện viên | Tổng hợp: 5 persona × kịch bản × lỗi; sinh bằng mô hình mở cho phép dùng đầu ra; lọc ràng buộc + LLM-judge | 200 → 8.000 SFT + 2.000 DPO | Đội tự tạo, CC BY 4.0 | Đánh giá; fine-tune (Pha D) |
| Ảnh giao diện có nhãn | Playwright render sandbox ở 6 kích thước, nhãn khung từ DOM | ~3.000 ảnh | Đội tự tạo, CC BY 4.0 | Đánh giá VLM |
| Kịch bản lừa đảo | Mẫu hành vi từ cảnh báo công khai của Bộ Công an, Hiệp hội An ninh mạng (không chép nguyên văn) | 10 → 20 × 5 biến thể | Đội tự tạo ở mức dấu hiệu (mục 4) | Vắc-xin lừa đảo |
| Giọng nói đánh giá | (a) Common Voice vi, (b) VIVOS: tải tự động, chỉ lưu manifest; (c) tự ghi 60–90 phút giọng ba miền, người 50+ (có phiếu đồng thuận) | 1 → 10 giờ | (a) CC0; (b) CC BY-NC-SA 4.0 — chỉ đánh giá, không phân phối lại; (c) CC BY | WER theo lát cắt |
| Dữ liệu pilot | Phiếu đồng thuận chữ to; log ẩn danh theo mã số, SUS, điểm vắc-xin; không ghi âm | 5–10 → 30 người | Không công bố; xóa sau 90 ngày | Kết quả thử nghiệm |

## 3.2. Căn cứ bảo đảm tính hợp lệ

- **Nguồn gốc:** mỗi trang có `source_type` (QPPL / cơ quan nhà nước / ngân hàng), ngày kiểm tra robots.txt và điều khoản sử dụng (trang ngân hàng chỉ dùng khi không bị cấm); pipeline cảnh báo khi hash nguồn đổi.
- **Được phép sử dụng:** dữ liệu đội tự tạo phát hành CC BY 4.0 kèm mã Apache-2.0; VIVOS kê khai phi thương mại, không vào repo; mô hình sinh dữ liệu có điều khoản cho phép dùng đầu ra (ghi trong Bản kê khai).
- **Dữ liệu cá nhân:** không thu CCCD, số tài khoản, OTP, mật khẩu; người học dùng biệt danh; giọng nói chuyển thành chữ trong bộ nhớ, không lưu audio; ảnh màn hình sống 60 giây; dữ liệu pilot ẩn danh, không công bố.
- **Giấy phép mô hình:** đối chiếu thẻ mô hình, ghi SPDX trong `data/registry/models.yaml` (Qwen3.5 Apache-2.0; PhoWhisper BSD-3-Clause; bge-m3, bge-reranker MIT; YOLOX Apache-2.0; Piper MIT); `make audit` từ chối AGPL/GPL/CC-NC ở thành phần chạy sản phẩm.

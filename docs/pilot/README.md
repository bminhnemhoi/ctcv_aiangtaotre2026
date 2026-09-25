# docs/pilot — Thiết kế thử nghiệm với người thật (plan §9 + idea §8, điều chỉnh theo ADR-006)

Epic tương ứng: `epics/PILOT.md`. Tài liệu buổi học được sinh bởi `make pilot-kit` vào `eval/pilot/kit/`; báo cáo bởi `make pilot-report` vào `eval/pilot/report.md`. Thư mục này chỉ giữ thiết kế, nguyên tắc đồng thuận và lịch; **không** chứa dữ liệu pilot.

## 1. Hai tầng (ADR-006 mục 3; C01-gap, C13, S3)
| Tầng | Khi | Ai | Thiết kế | Dùng cho |
| --- | --- | --- | --- | --- |
| 1 — sơ bộ | 26–27/9/2026 (T7–CN) | n = 5–10 người thân/hàng xóm 50+, có đồng thuận | 1 buổi 90 phút + ôn ngày 2 (thẻ QR); không nhóm đối chứng | Mục 8 hồ sơ 29/9: ghi rõ "sơ bộ, n = …", không suy diễn thống kê; MOS TTS; lỗi cần sửa |
| 2 — chính thức | Pha D: buổi 1 T7 31/10, ôn ngày 2 (2/11) và 5 (5/11), buổi 2 T5 5/11; báo cáo 9/11 (cửa sổ 27/10–9/11) | 30 người 50+ qua Đoàn phường / Đoàn trường TDTU | Ngẫu nhiên A (TNV + CTCV) / B (TNV theo cách hiện tại) theo mã lẻ/chẵn; cùng 4 kỹ năng, cùng thời lượng; B dùng CTCV sau khi đo | "Xác minh sản phẩm" chung kết; hồ sơ cập nhật nếu BTC cho phép (N02) |

plan §9 đặt pilot ở D17–D19 (4–6/10, sau hạn nộp, buổi 2 cách 2 ngày) — thay bằng thiết kế idea §8 (buổi 2 = +5 ngày, ôn ngày 2/5) để KPI "quay lại ngày 5" đo được (C13/S12).

## 2. Lịch buổi (tầng 2; tầng 1 rút gọn theo PILOT.md)
| Buổi | Thời lượng | Nội dung | Số đo |
| --- | --- | --- | --- |
| 1 | 120' | Đồng thuận (10') · kiểm tra đầu vào bằng giọng nói (10') · kỹ năng 1–2 (80') · SUS ngắn (10') · điểm vắc-xin trước (10') | baseline, thời gian, số lần trợ giúp, SUS |
| Ôn ngày 2 và 5 | 2' × 2 | Bài ôn qua **thẻ giấy + QR** không cần đăng nhập (không Zalo — ETH-12) | tỷ lệ quay lại theo mã lớp |
| 2 (= buổi 1 + 5 ngày) | 120' | Kiểm tra lại 1–2 (20') · kỹ năng 3–4 (70') · vắc-xin lừa đảo (20') · phỏng vấn 5 câu (10') | tự hoàn thành lần 2, điểm vắc-xin sau, phản hồi |

## 3. Nguyên tắc đồng thuận và dữ liệu (ADR-005)
- Phiếu đồng thuận **chữ to** 1 trang, mã số thay tên; họ tên chỉ trên phiếu giấy do trưởng nhóm giữ, hủy sau 90 ngày; `display_name` trong hệ thống là biệt danh/mã do TNV cấp.
- Câu bắt buộc trên phiếu: "Giọng nói được chuyển thành chữ ngay và không được lưu"; ô riêng cho ghi âm (chỉ để làm tập đánh giá CC-BY / hướng phát triển) và ô riêng cho ảnh câu chuyện người học.
- Không ghi âm/ghi hình nếu không tick ô riêng; không thu CCCD, SĐT, tài khoản; quyền xóa dữ liệu qua TNV theo mã số.
- Dữ liệu thô (log sandbox, SUS nhập, bấm giờ nhóm B) ở máy chủ trong nước, xóa sau 90 ngày; **không bao giờ** lên Google Drive/repo (D21); báo cáo chỉ chứa số tổng hợp và trích dẫn ẩn danh.
- Người cao tuổi là nhóm dễ tổn thương: không áp lực thời gian, không xếp hạng công khai, lời nhắc khích lệ; nhóm B vẫn được học và dùng CTCV sau khi đo (công bằng).
- Cơ sở pháp lý dẫn trong phiếu/hồ sơ chỉ từ `docs/legal/refs.yaml` có `verified_on`.

## 4. `make pilot-kit` sinh gì (`eval/pilot/kit/`)
1. Phiếu đồng thuận chữ to (docx/pdf, ≥ 20 pt).
2. Checklist dẫn lớp cho TNV (theo phút).
3. Bảng phân công 3 thành viên + 2 TNV Đoàn (người dùng: điều phối + kỹ thuật; thành viên 2: nhóm A; thành viên 3: nhóm B + bấm giờ).
4. Hướng dẫn thiết bị: mượn 10 máy tính bảng hoặc dùng điện thoại người học; **kiểm tra kết nối tại địa điểm** trước 1 ngày; nếu mất mạng → PWA offline 6 kịch bản (E12), thiếu máy → 2 người/máy.
5. Thẻ nhắc "3 việc phải làm khi bị gọi lừa đảo" (in).
6. Ứng dụng bấm giờ cho nhóm B (trang web nhỏ trong `apps/web`).
7. Mẫu ghi chú quan sát.
8. Thẻ giấy + QR bài ôn ngày 2/5 (không đăng nhập).

## 5. `make pilot-report` sinh gì (`eval/pilot/report.md` + PNG)
Bảng trước/sau: tự hoàn thành lần 2 (mục tiêu ≥ 70 %), thời gian và số bước sai (giảm ≥ 40 %), phút TNV/người/kỹ năng (giảm ≥ 50 %, từ bấm giờ), điểm dễ tổn thương trước/sau (giảm ≥ 40 %), SUS (≥ 70), quay lại ngày 5 (≥ 50 %), MOS TTS; khoảng tin cậy bootstrap; biểu đồ; trích dẫn ẩn danh; bảng KPI đạt/không đạt so idea §8; mục "kết quả chưa đạt"; n < 30 → tự chèn nhãn "sơ bộ". Mọi số truy vết về bảng `sessions`/`drills` (không PII).

## 6. Kết quả cần đưa vào hồ sơ
Bảng KPI; biểu đồ trước/sau; 3 câu chuyện người học có ảnh (đã tick ô đồng ý); danh sách lỗi phát hiện và đã sửa trước bản nộp/chung kết.

## 7. Việc của người (bắt đầu 18/9 vì chờ lâu — S8, N16)
- Thành viên 2: liên hệ Đoàn phường/TDTU xin lịch tầng 2 (giữ T7 31/10 và T5 5/11), in phiếu, mượn thiết bị.
- Người dùng: tìm 5–10 người thân/hàng xóm 50+ cho tầng 1 (26–27/9), ưu tiên đủ 2 miền giọng.
- Thành viên 3: dẫn tầng 1, nhập SUS, đối chiếu số liệu với `eval/pilot/report.md`.

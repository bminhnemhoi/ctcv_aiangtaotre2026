# PILOT — Thử nghiệm với người thật (hai tầng: sơ bộ n = 5–10 và chính thức 30 người)

## Mục tiêu
Có số đo người thật, trung thực và có đồng thuận, cho mục 7–9 MẪU 3: tầng 1 **sơ bộ** n = 5–10 người thân/hàng xóm 50+ trước hạn nộp (ghi rõ quy mô, không suy diễn thống kê); tầng 2 **chính thức** 30 người qua Đoàn phường/Đoàn trường TDTU ở Pha D, thiết kế nhóm đối chứng, buổi 2 = buổi 1 + 5 ngày, ôn ngày 2/5 (C13/S12), phục vụ "xác minh sản phẩm" chung kết và hồ sơ cập nhật (nếu BTC cho phép — N02). `make pilot-kit` sinh toàn bộ tài liệu, `make pilot-report` sinh `eval/pilot/report.md` từ log.

## Đầu vào
- `docs/plan.md` §9 (thiết kế, lịch, tài liệu, vai trò, cách đo, dự phòng, kết quả cần đưa vào hồ sơ), §6 hàng Pilot; `docs/idea.md` §8 (thiết kế pilot 2 tuần, buổi 2 cách 3–5 ngày, KPI "quay lại ngày 5"), §3 (personas), §9 (đồng thuận, dữ liệu ẩn danh, máy chủ trong nước), §14 (dự phòng 10–15 người).
- `docs/decisions/E01-brief.md` D28 (`display_name` = biệt danh/mã do TNV cấp; retention 90 ngày), D30 (pilot hai tầng), D21 (dữ liệu pilot thô không bao giờ lên Drive/repo); ADR-005 (retention, xóa theo yêu cầu, in-country), ADR-006 (lịch); `docs/pilot/README.md`.
- Phát hiện S3 (bằng chứng thay thế), C01-gap (pilot hai tầng), C13 (buổi 2 = +5 ngày), ETH-12 (bỏ Zalo khỏi pilot; thẻ giấy + QR ôn tập; đo "quay lại" bằng mã lớp; ASR không lưu audio), N08 (đội hình), S8 (phân công thành viên 2/3).
- Kết quả: tầng 1 cần E02, E03-lite, E04, E05 (bản 25/9); tầng 2 cần E09, E10 đủ, E11 đủ, E12 prod.

## Công việc
1. `make pilot-kit` (điểm vào `python -m ctcv_eval.pilot kit` đúng như Makefile gọi; mở rộng module `ctcv_eval.pilot` mà E01 để stub — không tạo `pilot_kit.py` riêng → `eval/pilot/kit/`): phiếu đồng thuận chữ to 1 trang (mã số thay tên; ô riêng cho ghi âm; câu "giọng nói được chuyển thành chữ ngay và không lưu"; quyền xóa qua TNV), checklist dẫn lớp cho TNV, bảng phân công 3 thành viên, hướng dẫn thiết bị (mượn 10 máy tính bảng hoặc dùng điện thoại người học; kiểm tra kết nối địa điểm thay cho APK — C02-gap), thẻ nhắc "3 việc phải làm khi bị gọi lừa đảo", ứng dụng bấm giờ nhóm B (trang web nhỏ trong `apps/web`), mẫu ghi chú quan sát, thẻ giấy + QR ôn tập không cần đăng nhập (thay Zalo).
2. Tầng 1 (26–27/9, 1 buổi 90 phút + ôn ngày 2): đồng thuận (10') → kiểm tra đầu vào bằng giọng nói (5') → 2 kỹ năng trong sandbox (50') → 3 drill (10') → SUS ngắn + MOS TTS 5 câu (10') → phỏng vấn 3 câu; đo: hoàn thành, số bước sai, số lần gợi ý, thời gian, SUS, MOS; ghi rõ "sơ bộ, n = …" trong mục 8.
3. Tầng 2 (Pha D): 30 người 50+, chia ngẫu nhiên A (TNV + CTCV) / B (TNV theo cách hiện tại) theo mã lẻ/chẵn; cùng 4 kỹ năng, cùng thời lượng; B được dùng CTCV sau khi đo. Buổi 1 (120'): đồng thuận, kiểm tra đầu vào, kỹ năng 1–2, SUS, điểm drill trước; ôn ngày 2 và ngày 5 bằng thẻ QR (bài 2 phút không đăng nhập, đếm "quay lại" theo mã lớp); buổi 2 = buổi 1 + 5 ngày (120'): kiểm tra lại 1–2, kỹ năng 3–4, drill sau, phỏng vấn 5 câu.
4. `make pilot-report` (`python -m ctcv_eval.pilot report`, cùng module → `eval/pilot/report.md`): bảng trước/sau (tự hoàn thành lần 2, thời gian, số bước sai, điểm drill, SUS, quay lại ngày 5), khoảng tin cậy bootstrap, biểu đồ PNG, trích dẫn phản hồi ẩn danh; so KPI idea §8 (≥ 70 % tự hoàn thành, giảm ≥ 40 % thời gian/bước sai, giảm ≥ 40 % "sập bẫy", SUS ≥ 70, quay lại ≥ 50 %); mục "kết quả chưa đạt".
5. Dữ liệu: log sandbox theo mã số (`display_name` biệt danh), SUS giấy nhập bằng biểu mẫu, nhóm B qua bấm giờ; không ghi âm nếu không có ô đồng ý riêng; dữ liệu thô ở máy chủ trong nước, xóa sau 90 ngày (`make backup` không chép dữ liệu pilot ra Drive/repo); họ tên chỉ trên phiếu giấy do trưởng nhóm giữ, hủy sau 90 ngày.
6. Vai trò tại lớp: người dùng điều phối + kỹ thuật; thành viên 2 dẫn nhóm A (và lo giấy tờ/đối tác pilot/phiếu đồng thuận từ 18/9 — S8); thành viên 3 dẫn nhóm B + bấm giờ (và soát 13 mục hồ sơ); 2 TNV Đoàn hỗ trợ.
7. Kịch bản dự phòng: chỉ 10–15 người → giữ thiết kế, báo cáo rõ quy mô; lớp mất mạng → PWA offline (E12) cho 6 kịch bản; thiếu thiết bị → 2 người/máy, ghi nhận.

## Đầu ra
`eval/pilot/kit/` (tài liệu in được), `eval/pilot/report.md` + PNG (tầng 1 bản "sơ bộ", tầng 2 bản đầy đủ), 3 câu chuyện người học có ảnh (đã xin phép), danh sách lỗi phát hiện và đã sửa trước bản nộp/chung kết; số liệu được `make dossier` nhúng vào mục 8 qua placeholder `{{eval:pilot.*}}`.

## Test nghiệm thu (tự động, phải xanh)
- `uv run pytest eval` — `ctcv_eval.pilot` (lệnh `report`) tính đúng bảng trước/sau và bootstrap trên fixture log giả; báo cáo từ chối khi có cột PII; n < 30 → tự chèn dòng "quy mô sơ bộ, không suy diễn thống kê".
- `make pilot-kit` — sinh đủ 8 tài liệu; phiếu đồng thuận có cỡ chữ ≥ 20 pt (kiểm bằng script đọc docx/pdf) và có ô ghi âm riêng.
- `make pilot-report` — sinh `eval/pilot/report.md` từ log thật (tầng 1: n = 5–10; tầng 2: ≥ 30 — plan §6 "báo cáo sinh tự động từ log, ≥ 30 người"); mọi con số truy vết được về bảng `sessions`/`drills`.
- `uv run pytest tests/invariants` — bất biến (b): không PII trong log pilot mẫu.
- `make check QUICK=1` xanh (mã pilot-kit/report có test đơn vị).

## Không được làm
Lưu họ tên/SĐT/CCCD học viên trong hệ thống; ghi âm không có đồng thuận riêng; đưa dữ liệu pilot thô lên Drive/repo (D21); gửi tin qua Zalo từ hệ thống (ETH-12); tạo áp lực thời gian hay xếp hạng công khai; suy diễn thống kê từ n < 30; dời buổi 2 dưới 3 ngày hoặc quá 7 ngày sau buổi 1; dùng dữ liệu pilot để train.

## Câu hỏi mở (≤ 3)
1. Đối tác tầng 2: Đoàn phường nào hay Đoàn trường TDTU — ai xin lịch, hạn chốt địa điểm (cần trước 20/10)?
2. Tầng 1: ai là 5–10 người thân/hàng xóm; có đủ 2 miền giọng để báo cáo MOS/WER sơ bộ không?
3. Nhóm B (đối chứng) có chấp nhận được về đạo đức với Đoàn phường (họ vẫn được học, dùng CTCV sau khi đo)?

## Checklist cho người dùng (≤ 30 phút)
- [ ] Đọc phiếu đồng thuận chữ to; ký thử với một người thân; câu chữ có dễ hiểu không?
- [ ] Chạy thử buổi tầng 1 với 1 người trong nhà theo checklist dẫn lớp; bấm giờ xem 90 phút có đủ không.
- [ ] Sau buổi: mở `eval/pilot/report.md`, so 3 con số với ghi chú tay.
- [ ] Gọi đối tác pilot tầng 2 để giữ 2 ngày (T7 31/10 và T5 5/11) — việc của người.

## Mốc thực tế
Tầng 1: 26–27/9/2026 (T7–CN), sau E05/E09-lite/E10-lite, trước khi quay video và chốt hồ sơ 28–29/9. Tầng 2: Pha D — buổi 1 T7 31/10, ôn ngày 2 (2/11) và ngày 5 (5/11), buổi 2 T5 5/11, `make pilot-report` 9/11; cửa sổ cho phép 27/10–9/11 (ADR-006). plan §6/§9 ghi D17–D19 (= 4–6/10, sau hạn nộp và sát hackathon) với buổi 2 cách 2 ngày — thay bằng thiết kế idea §8 (+5 ngày) theo C13.

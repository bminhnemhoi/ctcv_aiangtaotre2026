---
name: fix
description: Sửa lỗi khi CI đỏ hoặc lỗi runtime theo kiểu debugger — tái hiện bằng test thất bại, cô lập, sửa tối thiểu ở nguyên nhân gốc, test hồi quy, make check; tối đa 3 vòng rồi báo. Chỉ gọi tay bằng /fix.
argument-hint: "[mô tả lỗi | đường dẫn log | 'CI']"
disable-model-invocation: true
---
Lỗi: $ARGUMENTS (hoặc lấy từ CI/log mới nhất: `gh run list --limit 3`, `gh run view <id> --log-failed`, `docs/status/errors.log`, `docs/status/last_check.json`). Quy trình: **tái hiện bằng test thất bại** (tên tiếng Anh mô tả, đặt cạnh mã lỗi) → cô lập vị trí bằng subagent chỉ đọc (`reviewer` hoặc `architect`) nếu cần đọc nhiều file → sửa **tối thiểu ở nguyên nhân gốc**, không sửa triệu chứng, không đổi contract/schema/config bảo mật → test hồi quy giữ lại → `uv run pytest <thư mục>` rồi `make check QUICK=1`. Nếu lỗi thuộc red-team/pilot: test hồi quy vào `eval/redteam/` hoặc `tests/invariants/` trước khi sửa. Tối đa **3 vòng**; nếu chưa xong, báo tôi kèm log 30 dòng cuối, giả thuyết còn lại và 2 hướng xử lý. Không xóa/bỏ qua test, không nới ngưỡng eval, không đổi cấu hình bảo mật (hook, permissions, guardrails) để cho xanh, không `--no-verify`. Kết thúc ≤ 10 dòng: nguyên nhân gốc, thay đổi (file), test hồi quy (tên), kết quả `make check`, rủi ro còn lại; ghi vào CHANGELOG nếu ảnh hưởng người dùng.

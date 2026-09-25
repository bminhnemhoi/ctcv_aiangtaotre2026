---
name: refactor
description: Tái cấu trúc một mô-đun đang phình của CTCV — chỉ khi có test bao phủ, giữ hành vi và API công khai, giảm phức tạp, đo trước/sau (dòng, hàm > 50 dòng, cyclomatic). Chỉ gọi tay bằng /refactor.
argument-hint: "<đường dẫn mô-đun hoặc thư mục>"
disable-model-invocation: true
---
Mục tiêu: $ARGUMENTS. Điều kiện tiên quyết: mô-đun có test bao phủ (`uv run pytest <thư mục> --cov=<gói>`; thiếu → viết test đặc tả hành vi hiện tại trước, không refactor "mù"). Đo **trước**: số dòng, số hàm > 50 dòng, độ phức tạp (`uv run ruff check --select C901 --config "lint.mccabe.max-complexity=10" <đường dẫn>`), thời gian test. Quy tắc: giữ nguyên hành vi và API công khai (tên hàm/route/schema/config); tách hàm ≤ 50 dòng, docstring tiếng Anh; dùng `ctcv_core` thay vì mã trùng; không đổi contract brief §3–§9, không đụng migration đã merge, không đổi `config/eval.yaml`, guardrails hay hook; không thêm thư viện. Mỗi bước nhỏ: sửa → `uv run pytest` → tiếp; kết thúc `make check QUICK=1`. Đo **sau** và trình bảng trước/sau; nếu một chỉ số xấu đi, giải thích hoặc hoàn lại. Gọi `reviewer` đọc diff (hành vi không đổi, test không bị nới); chạm `services/agent` → `security-redteam`. Kết thúc ≤ 10 dòng: bảng trước/sau, file đã đổi, test, rủi ro; ghi CHANGELOG mục "Changed" nếu cấu trúc mô-đun đổi.

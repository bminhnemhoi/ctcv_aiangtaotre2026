# Đóng góp cho CTCV

Cảm ơn bạn quan tâm đến CTCV. Tài liệu này mô tả cách đề xuất thay đổi sao cho dự án giữ được chất lượng mức sản phẩm và ba nguyên tắc bất biến. Tham gia dự án đồng nghĩa với đồng ý tuân theo [Bộ quy tắc ứng xử](CODE_OF_CONDUCT.md).

## Trước khi bắt đầu

- **Báo lỗi, đề xuất tính năng:** mở GitHub Issue, mô tả bước tái hiện, kết quả mong đợi và kết quả thực tế. **Không** dán câu hỏi thật của người dân, số định danh, số điện thoại hay ảnh màn hình chưa che thông tin cá nhân.
- **Lỗ hổng bảo mật:** không mở issue công khai — dùng GitHub Security Advisories theo [SECURITY.md](SECURITY.md).
- **Thay đổi lớn** (kiến trúc, mô hình, schema dữ liệu, thêm tool cho agent, thêm thư viện, đổi ngưỡng đánh giá): mở issue thảo luận trước; quyết định được ghi thành ADR (xem dưới).

## Chuẩn bị môi trường

Yêu cầu: Git, [uv](https://docs.astral.sh/uv/), Node ≥ 20 + pnpm ≥ 10, Ollama (chỉ khi chạy demo hoặc đánh giá có mô hình), GNU make (Windows: `winget install ezwinports.make`, chạy trong Git Bash).

```bash
uv sync --all-packages      # Python 3.12 + mọi gói trong uv workspace
pnpm install                # workspace web
uv run pre-commit install   # ruff, prettier, gitleaks chạy trước mỗi commit
```

Chạy thử sản phẩm: xem [docs/DEMO.md](docs/DEMO.md).

## Quy trình làm việc

1. **Nhánh:** tách từ `main`, đặt tên `epic/E0X-ten-ngan` cho việc thuộc một epic, hoặc `fix/<mo-ta-ngan>`, `docs/<mo-ta-ngan>` cho việc nhỏ.
2. **Test trước, mã sau:** viết test thể hiện hành vi mong muốn (hoặc tái hiện lỗi), thấy test đỏ, rồi mới sửa mã. Mọi lỗ hổng tìm thấy phải có ca hồi quy trước khi sửa.
3. **Kiểm tra cục bộ:** `make check QUICK=1` phải xanh trước khi mở PR (lint · unit · integration · red-team guardrail · audit · docs-check). Trong lúc làm có thể chạy từng phần: `uv run pytest services/agent`, `pnpm test`.
4. **Commit:** theo [Conventional Commits](https://www.conventionalcommits.org/), tiếng Anh, có tiền tố epic khi có:
   `[E05] feat(agent): verify fee validity date before reading amounts`
   Kiểu thường dùng: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `ci`.
5. **Pull request:** điền đủ 4 mục của `.github/PULL_REQUEST_TEMPLATE.md` — làm gì, test thế nào, checklist ≤ 30 phút cho người duyệt, rủi ro. Cập nhật `CHANGELOG.md` (mục `[Unreleased]`) và README của mô-đun bị ảnh hưởng.

## Quy ước mã

- **Ngôn ngữ:** tiếng Anh cho mã, tên biến, docstring, commit; tiếng Việt cho giao diện, thông điệp lỗi, tài liệu và ADR.
- **Python 3.12:** gói `src/` layout, hatchling, một `uv.lock` chung; định dạng và lint bằng `ruff`. Mã dùng chung đặt ở `libs/core` (`ctcv_core`), không sao chép vào từng dịch vụ.
- **Web:** TypeScript strict, React 18, Tailwind 3; `eslint` + `prettier`. Chữ lớn, vùng bấm lớn — người dùng chính là người cao tuổi.
- **Hàm ≤ 50 dòng.** Không hard-code URL, tên mô hình, ngưỡng hay cổng: mọi giá trị đặt trong `config/*.yaml`, có JSON Schema và test.
- **Coverage ≥ 80 %** cho `services/agent`, `services/api`, `sandbox`. Không xóa, `skip` hay `xfail` test để cho xanh; không nới ngưỡng trong `config/eval.yaml` để qua cổng.
- **Thư viện mới** chỉ được thêm khi có trong `config/allowed-deps.yaml` kèm giấy phép thật; cấm AGPL/GPL/CC-NC ở runtime.

## Ba nguyên tắc bất biến

Mọi thay đổi phải giữ nguyên ba nguyên tắc sau và test bảo vệ chúng trong `tests/invariants/`:

1. Agent không có tool nào hành động trên hệ thống thật hay tài khoản thật; sandbox là hệ thống giả lập tách biệt.
2. Không lưu dữ liệu định danh (CCCD, số tài khoản, OTP, mật khẩu); ảnh màn hình che PII và xóa sau 60 giây.
3. Mọi dữ kiện đọc cho người dân phải có trích dẫn; không có nguồn thì trả lời "không chắc" và escalate.

Thay đổi guardrail, tool, prompt hệ thống (`config/prompts/`) hoặc `config/guardrails.yaml` phải chạy lại red-team: `uv run python -m ctcv_eval.redteam`.

## Không commit bí mật và dữ liệu cá nhân

- Bí mật chỉ nằm trong `.env` (đã gitignore; mẫu ở `.env.example`) hoặc GitHub Secrets. gitleaks chạy ở pre-commit và `make audit`.
- Không commit dữ liệu thủ tục thô hay đã chuẩn hóa (`data/raw`, `data/clean`) — nguồn không cho phân phối lại; pipeline tự tái tạo.
- Không commit dữ liệu người dùng thật, ảnh màn hình chưa che PII, thông tin cá nhân của thành viên đội.
- Số liệu trong tài liệu phải truy về file trong `eval/reports/` hoặc `data/registry/`; không có nguồn thì ghi "chưa đo".

## Ghi quyết định bằng ADR

Quyết định kỹ thuật lớn được ghi ở `docs/decisions/ADR-xxx-ten-ngan.md`, tối đa một trang, theo mẫu [ADR-000-template.md](docs/decisions/ADR-000-template.md): bối cảnh, lựa chọn, phương án bị loại, hệ quả, trạng thái (`đề xuất` → `chấp nhận` / `thay thế bởi ADR-yyy`). ADR bắt buộc khi đổi mô hình, schema dữ liệu, ngưỡng đánh giá, thêm tool cho agent hoặc thay đổi quy trình CI.

Ý tưởng ngoài phạm vi hiện tại ghi vào [docs/decisions/BACKLOG.md](docs/decisions/BACKLOG.md) thay vì mở rộng PR.

## Giấy phép đóng góp

Đóng góp của bạn được phát hành theo [Apache License 2.0](LICENSE), cùng giấy phép với dự án (điều 5 của giấy phép).

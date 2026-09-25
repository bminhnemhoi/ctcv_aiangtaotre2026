# ADR-008 — Lịch vòng 2–4 Data for Life 2026 và ba lỗi nền của cổng audit

Ngày: 2026-09-25 · Người quyết: **người dùng** (chưa quyết) · Trạng thái: **đề xuất** · Liên quan: ADR-007 (và phụ lục `ADR-007-hop-dong.md`), ADR-006 (hết hiệu lực phần lịch), D26 (allowed-deps), `docs/competition/DFL-2026-yeu-cau.md` §1.2, `Makefile` target `audit`

## Bối cảnh
**Lịch.** Các nguồn chính thức mâu thuẫn nhau (`DFL-2026-yeu-cau.md` §1.2, truy cập 25/9/2026). Thể lệ (Điều 8) ghi: vòng 1 từ 15/8 đến 20/9; vòng 2 từ 25/9 đến 06/11; vòng 3 đầu tháng 11; vòng 4 từ 20 đến 25/11. Trang chủ (Lộ trình) ghi: vòng 1 từ 28/8 đến 25/9; vòng 2 từ 28/9 đến 25/10; vòng 3 trung tuần tháng 11 (03–05 ngày); vòng 4 một ngày. Form nộp ghi hạn 25/09/2026, không ghi giờ. Thể lệ cho phép Ban Tổ chức điều chỉnh lịch và thông báo công khai. Chưa thấy thông báo gia hạn.

**Cổng audit.** `make check QUICK=1` còn đỏ ở bước `audit` vì ba lỗi có từ trước, không do mã DFL gây ra:
1. `config/allowed-deps.yaml` thiếu 648 gói đã có sẵn trong `uv.lock` và `pnpm-lock.yaml` (20 gói Python, 628 gói Node; không gói nào mang giấy phép GPL, AGPL hay NC). Bản ghép đã chuẩn bị ở scratchpad phiên 25/9 (`allowed-deps.proposed.yaml`), **chưa áp**.
2. gitleaks bắt khóa giả (`generic-api-key`) ở `.claude/hooks/tests/test_hooks.py:403`. Đây là fixture để kiểm hook chặn secret.
3. `pnpm audit --audit-level high` báo GHSA-fx2h-pf6j-xcff: vite ≤ 6.4.2 (repo dùng `^5.4.0`), lỗi vượt `server.fs.deny` trên Windows. Lỗi chỉ ảnh hưởng dev server; bản build tĩnh không chứa vite. `vite.config.ts` đang đặt `host: true`, nên dev server mở ra mạng LAN.

Sửa `config/allowed-deps.yaml`, `.gitleaks.toml`, `.claude/**` hay cấu hình audit là **điểm dừng**. Chỉ người dùng được quyết.

## Lựa chọn
Đề xuất, **chưa áp dụng**. Người dùng chọn từng mục:

- **Lịch:** coi 25/9 là hạn cứng của vòng 1 và nộp trước 12:00. Chuẩn bị cho vòng 2 bắt đầu **sớm nhất 25/9** (theo thể lệ) và **muộn nhất 28/9** (theo trang chủ). Kế hoạch vòng 2 lấy mốc kết thúc sớm hơn là 25/10; chỉ lùi khi Ban Tổ chức thông báo.
- **Lỗi 1:** (a1) áp bản ghép 648 mục sau khi người dùng xem lướt 28 mục `runtime: true`; không thêm gói mới. (a2) Giữ nguyên, chấp nhận audit đỏ đến khi rà xong từng gói.
- **Lỗi 2:** (b1) thêm chú thích `# gitleaks:allow` ở đúng dòng fixture (sửa `.claude/**`). (b2) Thêm allowlist theo đường dẫn `.claude/hooks/tests/` vào `.gitleaks.toml`, phạm vi rộng hơn b1. (b3) Giữ nguyên.
- **Lỗi 3:** (c1) nâng vite lên ≥ 6.4.3; phải đổi `pnpm-lock.yaml` và kiểm lại `vite-plugin-pwa`, vitest và build. (c2) Tạm bỏ qua GHSA-fx2h-pf6j-xcff trong cấu hình audit, có hạn xem lại. Trong lúc đó, khi quay demo chạy `vite --host 127.0.0.1`.

Phương án loại: hạ `--audit-level`, hoặc bỏ bước `audit` khỏi `make check`. Cả hai cách đều nới cổng và trái CLAUDE.md.

## Hệ quả
- Chưa có quyết định thì báo cáo cổng giữ nguyên trạng: mọi bước khác phải xanh, riêng `audit` đỏ vì ba lý do trên. Không gói nào tự sửa.
- c1 chạm `pnpm-lock.yaml`, trái hợp đồng C0 của ADR-007 trong ngày 25/9, nên nếu chọn thì làm sau khi nộp.
- Nếu vòng 2 bắt đầu ngày 25/9, việc sau khi nộp (BACKLOG mục D) phải bắt đầu ngay.

## Trạng thái
2026-09-25: đề xuất (docs-writer, theo kế hoạch orchestrator). Chờ người dùng chọn a/b/c và ghi "chốt ngày …, bởi …".
2026-09-25 (khi phát hành repo công khai trên GitHub), chốt bởi người dùng:
- (a) **Chấp nhận:** bổ sung vào `config/allowed-deps.yaml` 648 gói đã có sẵn trong `uv.lock`/`pnpm-lock.yaml` (không thêm thư viện mới; không có GPL/AGPL/SSPL/BUSL); `scripts/check_deps.py` báo 82 gói Python + 628 gói Node hợp lệ.
- GitHub Actions tạm tắt trong Settings của repo cho tới vòng 2 (workflow `gate` cần runner GPU riêng); không sửa `.github/**`.
- Nhật ký prompt: repo công khai chỉ mang `docs/prompt-log/INDEX.md` (SHA-256 từng phiên) và `README.md`; bản ghi đầy đủ giữ riêng, cung cấp cho Ban Tổ chức khi được yêu cầu (`.gitignore`). Quyết định này thay quy tắc 5 trong `docs/prompt-log/README.md` ("`.gitignore` không bao giờ bỏ qua thư mục này") đối với repo công khai; hook vẫn ghi đủ bản ghi ở máy của đội và INDEX vẫn là bằng chứng toàn vẹn.
- (b) gitleaks trong `.claude/hooks/tests` và (c) GHSA vite 5: chưa quyết, vẫn theo phần Lựa chọn. Xem lại khi Ban Tổ chức công bố lịch vòng 2 hoặc kết quả vòng 1, hoặc khi `pnpm audit` đổi kết quả.

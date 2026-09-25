# ctcv-kit — plugin Claude Code của Cầm Tay Chỉ Việc

**File sinh tự động** bởi `scripts/sync_plugin.py` (`make plugin`) từ `.claude/` — không sửa tay; sửa ở `.claude/` rồi chạy lại. Kiểm: `claude plugin validate plugins/ctcv-kit`.

## Cài vào repo mới (hackathon 2 ngày, thử thách 12 giờ)
```
claude --plugin-dir /đường/dẫn/ctcv/plugins/ctcv-kit
```
hoặc thêm thư mục này vào một marketplace nội bộ rồi `claude plugin install ctcv-kit@<marketplace>`.

## Nội dung
- `agents/` (11): architect, backend-dev, data-engineer, devops, docs-writer, eval-runner, frontend-dev, ml-trainer, qa-tester, reviewer, security-redteam. Frontmatter đã bỏ `hooks`, `mcpServers`, `permissionMode` (plugin không nhận ba trường này) — repo đích cần đặt lại trong `.claude/agents/` hoặc `settings.json` của nó nếu muốn `architect` ở plan mode và `frontend-dev`/`qa-tester` dùng MCP playwright.
- `skills/` (16): agent-security, coach-style, ctcv-conventions, daily, data-pipeline, dossier-btc, elder-ui, epic, fastapi-conventions, fix, hackathon-kit, incident, refactor, review, test-strategy, training-runbook.
- `hooks/hooks.json` (9 sự kiện) + `hooks/run.sh` + `hooks/*.py`: lệnh dùng `${CLAUDE_PLUGIN_ROOT}/hooks/run.sh`; hook ghi vào `docs/status/`, `docs/prompt-log/` của repo đích (tạo hai thư mục này; `protect-paths` cần marker `.claude/BOOTSTRAP` khi bootstrap).
- `.mcp.json`: chỉ `playwright` (Windows: `cmd /c npx …`; Linux thêm ở user scope: `claude mcp add playwright -- npx -y @playwright/mcp@latest --headless`).

## Repo đích cần có
`CLAUDE.md` (ba nguyên tắc bất biến, điểm dừng, Delegation), `.claude/settings.json` với `permissions` allow/deny của CTCV, `Makefile` có `check`/`redteam`/`daily`, `config/allowed-deps.yaml`, `training/budget.json` (hook budget tự tạo mặc định). Python ≥ 3.10 trên PATH cho hook.

---
name: harness-and-attack-setup
description: Ba cách chạy red-team lên CTCV (make redteam, live qua dev_cpu.py, inproc với FakeComposer) và mẹo gọi hook từ Python
metadata:
  type: reference
---

Ba kênh tấn công đã dùng cho gói P11-security:

1. **`make redteam`** (bắt buộc, không model): chạy `eval/redteam/scenarios.jsonl` qua `ctcv_agent.coach.run_turn` với `DummyPlanner` — planner "xấu nhất": nhại lại text và gọi đúng tool mà `context.planner_tools` khai. Chỉ guardrail + router + quarantine đỡ. Thêm kịch bản: định dạng dòng JSON có `id` dạng `XX-01`, `category` phải thuộc `CATEGORY_QUOTA` (chỉ để kiểm hợp lệ, không ép số lượng), `expected` ∈ {refuse, data_only, no_tool, escalate}, `check` là danh sách (vd `regex_absent:...`, `quarantined`, `no_tool_call`, `secret_hidden_from_planner`). Chấm tự động ở `eval/src/ctcv_eval/redteam/__init__.py::_grade_check`.

2. **Live qua stack thật**: `uv run python scripts/dev_cpu.py --no-web --run uv run python <script.py> <out.json>`. Script đọc `CTCV_DEMO_QR_TOKEN`/`CTCV_DEMO_STAFF_PASSWORD` từ env (dev_cpu sinh ngẫu nhiên mỗi lượt), gọi HTTP 127.0.0.1:8000. API cổng lấy từ `config/app.yaml`. **Nhớ**: nếu cổng 8000/5173 bận (stack người dùng), chỉ dựng khi rảnh, hoặc dùng kênh inproc. Kiểm log sau khi dừng: `%TEMP%/ctcv-dev-cpu/api.log`.

3. **Inproc** (nhanh, không cần stack, mô phỏng model bị lái): `AnswerEngine(FakeKnowledgeBase(records, DENSE, settings=s), FakeComposer([reply(...)]), s)`. `FakeComposer` nhận raw JSON `{"answer","doc_ids"}` — đây là cách ép "model bị lái" để kiểm lớp verify. Fixture thật: `services/agent/tests/fixtures/tthc/records/{1.004222,2.000200,1.004194}.json`; bản ghi đầy đủ ở `data/clean/tthc/records/`. Cho API/JWT: `fastapi.testclient.TestClient(create_app(Settings(_env_file=None, ...)))` + `build_services(kb=Fake..., composer=Fake...)`.

**Mẹo gọi hook từ Python trên Windows**: `subprocess.run(["bash", ...])` fail (WSL bash). Phải dùng đường tuyệt đối `r"C:\Program Files\Git\usr\bin\bash.exe"` rồi `.claude/hooks/run.sh <hook>`, đưa JSON PreToolUse qua stdin. Exit 2 = chặn. `guard` và `protect-paths` fail-closed.

Xem [[tthc-verify-layers]] và [[effective-attacks-tthc]].

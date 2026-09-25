# Chỉ mục prompt log

File này do hook `promptlog` (`.claude/hooks/promptlog.py`) sinh và cập nhật tự động — **không sửa tay** (BTC nghiêm cấm làm giả prompt log). Mỗi dòng: thời điểm UTC, đường dẫn file tương đối thư mục này (`sessions/<session_id>.jsonl`, `subagents/…`, `system/…`), SHA-256 của file, git HEAD lúc ghi, trạng thái (open/closed). `make promptlog-export` kiểm tra hash khớp trước khi đóng gói `07_PromptLog.zip` và đồng bộ lên Google Drive công khai (mục 13 MẪU 3).

| ts | file | sha256 | git_head | status |
| --- | --- | --- | --- | --- |
| 2026-09-24T07:40:53+00:00 | sessions/2d228d6b-8680-49fc-83d2-4f47729ac15c.jsonl | 6eebf204413d131bfa61a7b03c8d90d55d70feb00bb2e7d9ab2782c1c0ffdbeb | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a26739f420405342a.jsonl | 1077a099a96618daa9bfa81b568d28b99c654a50797dd5a6acd18a96f1cccab1 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a2acaf8fde94876b3.jsonl | 5ad88bfa1638b6443174cc891c87c39cf298290ba5ea947fc2f6204a609ed48d | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a315662186b733774.jsonl | 6bd3ac5f9421ea2f39e7c8dca544fec4459bb55707b27af0850f82661b161a86 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a4df7db21d49a5179.jsonl | a481c9bf5e104815f2cadd4f4866a2bbc87026131b7dbc23cb519e89fad5ea98 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a6a63be7833bfc018.jsonl | bde14b068f81a55380358ef4004f26982b2269639e520cd3a1ed20cd544fb538 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a87fb2d63563c89c3.jsonl | 1b4b8e275edfc5a7ed0075f0cc09049d20d49a99af3798db09746cdfcac55df5 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-a9396423b3635d339.jsonl | 8f1425d2187c7985022d61b783863ea616b2d8674bd2018ec273d4949dbe1745 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-ab6d116beb19f1bbc.jsonl | 2321eb1db0cc71a47f7254857c9f2b0fa52f86de402708615dce0480b657d783 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-ac2090e52f8502850.jsonl | c14b36fab6938c7ad4d019e520c090c07b2ea1314aafcad18fee73f91b3e720e | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-ac35c2161ddd568ea.jsonl | 70cbf67aa16821b8dd127a843b066b1011ee669b6bf5d7dbba499b820d82d71b | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-ad22a79385fafa371.jsonl | c3a0f90260b92f6d771f3df67c1a928d33f2670c0eebd8c9b64782723b572588 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-aefd5cc088cb4329a.jsonl | 2595f877429b873510beab24c1ce18988bbae4459a926f5da694cd43181a448e | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-af9c6255422a41a16.jsonl | 8aa30c9972043b01630e75740fdf07ce08b79b17e6f5b1b3de6e600e4b3c8750 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | subagents/2d228d6b-8680-49fc-83d2-4f47729ac15c-afb7281e252e626a2.jsonl | 8e21bb9ce8201eb3a278bf36c6c2fd29a6102c0cdfce0c8fd4765b0507aeeb48 | nogit | closed |
| 2026-09-24T07:40:53+00:00 | system/2d228d6b-8680-49fc-83d2-4f47729ac15c.json | b0170da06f7e5557160eda795a70d98291120f9965b656e459d96119a3c56171 | nogit | closed |
| 2026-09-24T20:54:35+00:00 | sessions/42a8ed58-aeab-497e-9a6e-2b46adf26261.jsonl | c97ebcf5f225c46f6ac7b0d2c248c8613000c5a7ebe877ddcab8a5bce153043b | nogit | imported |

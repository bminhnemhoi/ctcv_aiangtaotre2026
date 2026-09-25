# ctcv-core

Thư viện dùng chung cho mọi dịch vụ CTCV (brief D5). Không chứa logic nghiệp vụ.

| Module | Vai trò |
| --- | --- |
| `ctcv_core.config` | `load_config(name)` đọc `config/<name>.yaml`, kiểm JSON Schema 2020-12, cache, ghi đè bằng `CTCV_<NAME>_<KEY>` |
| `ctcv_core.errors` | `AppError(code, message_vi, status, details)` và các lớp con; `to_response()` trả `{"error": {"code", "message"}}` |
| `ctcv_core.logging` | `setup_logging(service)`: log JSON có `request_id`, bộ lọc `PiiScrubFilter` che CCCD/thẻ/OTP/điện thoại/email |
| `ctcv_core.paths` | `REPO_ROOT`, `CONFIG_DIR`, `SCENARIOS_DIR`, `DRILLS_DIR`, `REGISTRY_DIR`, `PROMPTS_DIR` |
| `ctcv_core.text` | `count_sentences()` cho tiếng Việt, `contains_banned_terms()` |
| `ctcv_core.version` | `__version__`, `get_version()` |

Chạy test: `uv run pytest libs/core -q`.

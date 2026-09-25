# ctcv-speech — dịch vụ giọng nói (ASR + TTS có cache)

Gói `ctcv-speech` (import `ctcv_speech`) phục vụ nghe (PhoWhisper qua faster-whisper) và đọc (TTS theo ADR-002) cho huấn luyện viên. **E01 chỉ dựng khung**: `/health` chạy thật, `POST /asr` và `POST /tts` trả `501 NOT_IMPLEMENTED` với thông điệp tiếng Việt cho tới E04 (`epics/E04.md`).

## Đường dẫn

| Method | Path | E01 | Ghi chú |
| --- | --- | --- | --- |
| GET | `/health` | thật | `{status, service, version, checks{asr_model, tts_model, tts_cache}, models{asr, asr_small, tts}}`; `checks` là `skipped` khi chưa nạp model |
| POST | `/asr` | 501 | multipart `audio` → `AsrOut{text, confidence, accent_tag}` (E04) |
| POST | `/tts` | 501 | JSON `TtsIn{text, voice?}` → `TtsOut{audio_url, cached}` (E04) |

Cổng: `config/app.yaml: ports.speech` (8020). **Mọi** lỗi dùng thân thống nhất `{"error": {"code", "message"[, "details"]}}` (`ctcv_core.errors`):

| Tình huống | HTTP | `code` |
| --- | --- | --- |
| Thiếu file/thiếu trường, trường lạ (`TtsIn` cấm trường thừa), `text` chỉ toàn khoảng trắng | 422 | `VALIDATION_FAILED` (`details.fields`; thông điệp của validator tiếng Việt được giữ nguyên) |
| `text` dài hơn `TTS_MAX_TEXT_CHARS` | 422 | `VALIDATION_FAILED` (`details{fields, max_chars, chars}`) |
| Đường dẫn không tồn tại | 404 | `NOT_FOUND` |
| Sai method (vd `GET /asr`) | 405 | `METHOD_NOT_ALLOWED` (giữ header `Allow`) |
| Tính năng chưa mở | 501 | `NOT_IMPLEMENTED` (`details.epic = "E04"`) |

## Cấu hình

| Nguồn | Khóa | Ghi đè bằng env |
| --- | --- | --- |
| `config/models.yaml` | `models.asr.id` (`vinai/PhoWhisper-small`), `models.asr_small.id` (`PhoWhisper-tiny`, profile `cpu`), `models.tts.id` (`TBD-ADR-002`) | `ASR_MODEL`, `TTS_MODEL` |
| `config/app.yaml` | `ports.speech` | `SPEECH_PORT` (1–65535, chỉ chữ số) |
| — | thư mục cache TTS (mặc định `<tmp>/ctcv-tts`) | `TTS_CACHE_DIR` |
| — | độ dài tối đa của `text` một lần đọc (tạm thời `DEFAULT_TTS_MAX_TEXT_CHARS` = 1000; E04 chuyển vào `config/app.yaml`) | `TTS_MAX_TEXT_CHARS` (số nguyên dương) |

Giá trị env rỗng hoặc bắt đầu bằng `CHANGE_ME` được coi là chưa đặt (`.env.example`). Số nguyên chỉ nhận chữ số 0-9 (`1_000`, `+80`, chữ số Ả Rập-Ấn bị từ chối) và trả `ValidationFailed` tiếng Việt khi sai. `SpeechSettings.tts_decided` là `False` khi TTS vẫn là `TBD-ADR-002`.

## Khóa cache TTS

`ctcv_speech.cache.cache_key(text, voice=None)` = SHA-256 của `voice` + văn bản, cả hai đã chuẩn hóa (NFC, gộp khoảng trắng, bỏ đầu/cuối, casefold); `voice` là `None`/rỗng → giọng mặc định. `cache_path(dir, key, ext="wav")` → `<dir>/<2 ký tự đầu>/<key>.<ext>`; `key` bắt buộc là 64 ký tự hex thường đúng như `cache_key` sinh ra và `ext` chỉ gồm chữ/số (≤ 8 ký tự) — giá trị khác → `ValueError`, nên khóa không bao giờ mang được đoạn đường dẫn (`../`) vào thư mục cache. Văn bản rỗng → `ValueError`.

## Chạy và kiểm thử

```bash
uv run ctcv-speech                                    # uvicorn trên cổng ports.speech
uv run pytest services/speech --cov=ctcv_speech        # test + coverage
uv run ruff check services/speech && uv run ruff format --check services/speech
```

## Phụ thuộc nặng (E04)

`faster-whisper`, `torch` (chỉ nếu ADR-002 chọn TTS chạy torch), `piper-tts` được ghi dưới `[project.optional-dependencies] runtime` trong `pyproject.toml` ở dạng **chú thích** — chưa cài ở E01 (không GPU, giữ image nhẹ). Khi E04 mở, bỏ chú thích, thêm vào `config/allowed-deps.yaml` (D26) rồi `uv sync --package ctcv-speech --extra runtime`.

## Không được làm (E04)

Lưu audio người dùng ra đĩa hoặc gửi ra ngoài máy chủ đội; bỏ nút "Nói lại"; dùng TTS giấy phép NC khi chưa ghi trong ADR-002.

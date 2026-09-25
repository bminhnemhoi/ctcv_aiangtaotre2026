# Phụ lục ADR-007 — Hợp đồng chung

Chép nguyên văn khối SHARED_CONTRACTS của kế hoạch thi công ngày 25/9/2026 (orchestrator). Trạng thái đi theo ADR-007: **đề xuất — chờ người dùng duyệt**.

---

SHARED CONTRACTS — Phụ lục ADR-007. Mọi gói phải tuân theo; P7a chép nguyên văn phần này vào docs/decisions/ADR-007-hop-dong.md.

C0 — Luật chung
- Môi trường:
  - Dùng Git Bash. Đầu mỗi phiên chạy: export PATH="$HOME/.local/bin:$HOME/AppData/Roaming/npm:$LOCALAPPDATA/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$PATH".
  - Ollama ở http://localhost:11434 (bge-m3, qwen3.5:2b). API chạy cổng 8000, web cổng 5173 (config/app.yaml).
- Phạm vi sửa file:
  - Repo chưa có commit, không dùng worktree. Mỗi gói CHỈ sửa file trong files_owned và chỉ chạy test theo đường dẫn file của mình. Lỗi ở gói khác thì báo orchestrator, không tự sửa.
  - Không thêm thư viện (uv.lock chỉ đổi cạnh workspace do P0; pnpm-lock giữ nguyên).
  - Không sửa config/models.yaml, config/tools.yaml, config/eval.yaml, Makefile, .claude/**, CLAUDE.md, .github/**.
  - Không hard-code URL, model, ngưỡng, cổng, đường dẫn dữ liệu: đọc từ config/rag.yaml, config/app.yaml, data/sources.yaml.
- Quy tắc mã:
  - Dưới services/agent/src: không tên hàm, lớp hay module chứa send_money, transfer, sms, payment. tools/*.py không import httpx, requests, urllib, socket, subprocess.
  - Test trước, mã sau. Hàm ≤ 50 dòng. Mã và docstring tiếng Anh (ruff D, kiểu google); chuỗi hiển thị cho người dùng tiếng Việt đời thường.
  - Không xóa, skip hay xfail test. Sửa kỳ vọng lỗi thời phải ghi lý do.
  - Không lưu hay log nguyên văn câu hỏi. Không đọc hay in .env.
- Chạy lệnh dữ liệu bằng uv run python -m ctcv_data.pipeline <bước> [--online], KHÔNG dùng make data.

C1 — Đường dẫn
- Dữ liệu thô (gitignore): data/raw/tthc/manifest.jsonl · data/raw/tthc/bca/list_<LINH_VUC>.html · data/raw/tthc/bca/tthc_<matt>.html
- Dữ liệu sạch (gitignore): data/clean/tthc/records/<procedure_id>.json · data/clean/tthc/normalize_report.json · data/clean/tthc/index/{chunks.jsonl, vectors.f32, index_meta.json}
- Tập đánh giá (commit): eval/sets/samples/{qa_tthc.schema.json, qa_tthc.jsonl (sinh), qa_tthc_handwritten.jsonl (soạn tay)}
- Báo cáo: eval/reports/{latest.json, <YYYY-MM-DD>.md, ablation-tthc.json, ablation-tthc.md, calibration-tthc.md, env-tthc.json}
- Hồ sơ: nguồn ở docs/dossier/dfl/ (hình ở figures/*.png, video/loi-thoai.yaml, video/slides/*.html); bản dựng ở docs/dossier/out/dfl/ (gitignore); đội ở docs/dossier/private/team-dfl.yaml (gitignore).

C2 — Bản ghi TTHC v1
File config/schemas/tthc-record.schema.json: JSON Schema 2020-12, additionalProperties:false ở mọi cấp. Model tương ứng: ctcv_agent.rag.types.ProcedureRecord.
- schema_version: 1
- procedure_id: ^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$ — bằng ma_thu_tuc nếu có, không thì "bca-<matt>".
- ma_thu_tuc: str|null · ten: str (1..300) · linh_vuc: str|null · co_quan_thuc_hien: str|null
- cap_thuc_hien: "bo" | "tinh" | "xa" | null
- muc_do_dvc: str|null · doi_tuong: str|null
- cach_thuc: [{kenh: "truc_tiep"|"truc_tuyen"|"buu_chinh"|"khac", kenh_text: str, thoi_han: str|null, phi_le_phi: str|null, phi_vnd: [int ≥ 0], mo_ta: str|null}]
- trinh_tu: [str]
- thanh_phan_ho_so: [{doc_key: ^d\d{2}$, truong_hop: str|null, ten_giay_to: str (1..600), ban_chinh: int|null, ban_sao: int|null, mau: str|null}]
- yeu_cau_dieu_kien: str|null
- can_cu_phap_ly: [{so_hieu: str|null, ten: str}]
- bieu_mau: [{ten: str, url: ^https://}]
- ket_qua: str|null
- sections_raw: {nhãn: văn bản đã NFC, khoảng trắng gộp, ≤ 8000 ký tự}
- meta:
  - source_url (^https://), source_portal, agency, matt (^\d+$), linh_vuc_code: str|null
  - fetched_at: date-time UTC, hậu tố Z
  - sha256_raw và sha256_content: ^[0-9a-f]{64}$
  - updated_at: date|null; effective_date: date|null. Nguồn không công bố thì để null, không tự điền.
  - license_note; parser_version: "tthc-bca/1"
- Cách tính sha256_content: sha256(utf-8(json.dumps(bản ghi đã bỏ khóa "meta", ensure_ascii=False, sort_keys=True, separators=(",", ":")))).

C3 — Chunk và chỉ mục
- SECTIONS (thứ tự) và nhãn:
  - tong_quan = Thông tin chung
  - trinh_tu = Trình tự thực hiện
  - thanh_phan_ho_so = Thành phần hồ sơ
  - phi_le_phi = Phí, lệ phí
  - thoi_han = Thời hạn và cách thức nộp
  - dieu_kien = Yêu cầu, điều kiện
  - can_cu_phap_ly = Căn cứ pháp lý
  - bieu_mau = Biểu mẫu
- Chunk:
  - doc_id: "tthc-<procedure_id>-<section>-<part>" (≤ 64 ký tự, ^[A-Za-z0-9][A-Za-z0-9_.-]*$); kèm procedure_id, section, part: int.
  - title: "<ten> — <nhãn>".
  - text: "Thủ tục <ten> (mã <ma_thu_tuc|procedure_id>) — <nhãn>: <nội dung>".
    - Nội dung ≤ chunk_max_chars; mục dài tách thành part 0, 1, …
    - Mỗi dòng giấy tờ: "[d01] (<truong_hop>) <ten_giay_to> — bản chính: x, bản sao: y".
    - Mỗi dòng phí: "<kenh_text>: <phi_le_phi>". Mỗi dòng thời hạn: "<kenh_text>: <thoi_han>".
  - Metadata: url = meta.source_url, agency, source_portal, fetched_at, effective_date, skill: "dich-vu-cong", sha256_content.
  - Chunker tất định, phiên bản "tthc-chunk/1".
- Dòng i của chunks.jsonl ứng với hàng i của vectors.f32 (float32 little-endian, đã chuẩn hóa L2, kích thước n×dim).
- index_meta.json: {version: 1, built_at, chunker_version, embed_model_ref: "embed", embed_model_id: "BAAI/bge-m3", embed_serving_name, dim, n_chunks, records, records_sha256, vectors_sha256}.

C4 — Giao diện Python (import, không sửa bên ngoài gói chủ)
- ctcv_agent.rag.types (P2a):
  - SECTIONS, SECTION_LABELS, CachThuc, DocumentItem, LegalRef, FormRef, RecordMeta.
  - ProcedureRecord (.load(path), .content_sha256()), Chunk.
  - Hit{chunk, score (RRF), bm25_score, dense_score: float|None, rank}; SearchResult{hits, degraded: bool}.
  - Protocol KnowledgeBase:
    - search(query, top_k, *, procedure_id=None, sections=None) -> SearchResult
    - get_procedure(pid) -> ProcedureRecord|None
    - get_chunk(doc_id) -> Chunk|None
    - chunks_for(pid, sections=None) -> list[Chunk]
    - find_procedures(query, limit) -> list[tuple[ProcedureRecord, float]]
    - procedure_count() -> int
  - KnowledgeBaseNotReady(AppError "KB_NOT_READY", 503, "Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé.")
  - ProcedureNotFound(AppError "PROCEDURE_NOT_FOUND", 404, "Chưa tìm thấy thủ tục này trong kho, anh/chị thử gõ tên khác nhé.")
- ctcv_agent.rag.settings (P2a): RagSettings là frozen dataclass chứa các khóa C5 đã phân giải: đường dẫn tuyệt đối theo gốc repo; endpoint = biến môi trường serving.endpoint_env nếu có, không thì serving.endpoint; embed_model_id và compose_model_id lấy từ config/models.yaml theo model_ref. Hàm load_rag_settings(root=None).
- ctcv_agent.rag.query (P2a):
  - normalize_query(text, s): NFC, casefold, gộp khoảng trắng, thay cụm dialect_phrases chỉ khi khớp nguyên cụm.
  - fold_accents(text): bỏ dấu, đ→d.
  - content_tokens(text), syllable_bigrams(tokens), expand_synonyms(text, s).
- ctcv_agent.rag.chunker (P2a): CHUNKER_VERSION, chunk_record(record, max_chars).
- ctcv_agent.rag.fake (P2a): FakeKnowledgeBase(records, dense_by_procedure=None).
- ctcv_agent.rag.embed (P2b):
  - Protocol Embedder{model_id; embed(texts) -> list[list[float]]} (vector đã chuẩn hóa L2).
  - OllamaEmbedder(settings=None, transport=None), có .hosts_contacted.
  - HashEmbedder(dim=64).
  - EmbedderUnavailable(AppError "EMBEDDER_UNAVAILABLE", 503).
- ctcv_agent.rag.index (P2b): FileKnowledgeBase.load(settings=None, embedder=None); FileGuideIndex(kb) (hiện thực GuideIndex của tools); wire_default_backends(kb).
- ctcv_agent.rag.build (P2b): build_index(records_dir, out_dir, embedder, settings) -> BuildReport; chạy bằng `uv run python -m ctcv_agent.rag.build`.
- ctcv_agent.schemas.Citation (P2a) thêm các trường tùy chọn: agency, source_portal, fetched_at: datetime|None, section, procedure_id.
- tools (P2b): GuideChunk và GuideHit thêm trường tùy chọn procedure_id, section, agency, fetched_at, score. verify_citation.Output thêm agency, fetched_at, procedure_id, section.
- ctcv_agent.contracts (P2a):
  - Reason = Literal["ok", "no_source", "sensitive", "real_action", "pasted_content", "verify_failed", "kb_not_ready"]
  - AnswerMode = Literal["llm_verified", "llm_unverified", "template", "safety", "no_source"]
  - ProcedureRef{procedure_id, ten, co_quan: str|None, source_url, fetched_at: datetime}
  - DocItem{doc_key, name, case_label: str|None, originals: int|None, copies: int|None, form_code: str|None}
  - FeeItem{channel, channel_text, time_limit: str|None, fee_text: str|None, amounts_vnd: list[int]}
  - ProcedureCard (mở rộng ProcedureRef){documents: list[DocItem], fees: list[FeeItem], cases: list[str]}
  - AskDiagnostics{intent: str|None, retrieved_procedure_ids: list[str] (≤ 5, khác nhau), top_dense: float|None, match_score: float|None, gate_passed: bool, answer_core: str|None, composer_sentence: str|None, composer_doc_ids: list[str], composer_error: str|None, fallback_reason: str|None, degraded: bool, timings_ms: dict[str, float] (retrieve, compose, verify, total), hosts_contacted: list[str]}
  - AskResult{answer, citations: list[Citation], confidence (0..1), escalate, refused = False, reason, answer_mode, procedure: ProcedureCard|None, diagnostics}
  - IntakeRequest{procedure_id: str|None, query: str|None (2..200), received: list[str] (^d\d{2}$, ≤ 60, không trùng), case_label: str|None (≤ 300)} — phải có đúng một trong procedure_id và query.
  - ChecklistItem (mở rộng DocItem){status: "da_nhan"|"thieu"}
  - IntakeResult{procedure: ProcedureRef, alternatives: list[ProcedureRef] (≤ 3), cases, needs_case: bool, items: list[ChecklistItem], missing_count, message_for_citizen (≤ 2 câu), citations}
  - Protocol AnswerService.ask(question, ctx: SessionContext) -> AskResult; Protocol IntakeService.check(req) -> IntakeResult.
- ctcv_agent.ask (P3):
  - AnswerEngine(kb, composer, settings, mode=None); .route(q) -> RouteDecision{intent, procedure_id, dense, match, passed}.
  - build_engine(settings=None, *, mode=None, kb=None, composer=None). Mode "llm_unverified" chỉ bật khi truyền tường minh (dùng cho eval).
- ctcv_agent.intake (P3): IntakeChecker(kb).
- ctcv_agent.verify (P3): verify(claim, chunks, verifier=None, threshold=None) -> (score, ok) giữ chữ ký cũ, ok thêm điều kiện số ⊆ nguồn; evaluate_sentence(sentence, chunks, lexical_min) -> SentenceVerdict{numbers_ok, unsupported_numbers, lexical_score, lexical_ok, factual}.
- ctcv_agent.numeric (P3): canonical_numbers(text), numbers_supported(answer, sources).
- Câu cố định (P3):
  - NO_SOURCE_LINE: "Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức. Bác hỏi cán bộ một cửa hoặc tình nguyện viên giúp cháu nhé."
  - SENSITIVE_LINE: "Bác đừng đọc mã OTP, mật khẩu hay số thẻ cho ai, kể cả người xưng là cán bộ. Nếu thấy lạ, bác hỏi tình nguyện viên hoặc con cháu trước nhé."
  - REAL_ACTION_LINE: "Cháu không làm thay bác trên ứng dụng hay tài khoản thật được. Cháu chỉ từng bước để bác tự làm, bác cần hỏi thủ tục nào ạ?"
  - PASTED_LINE: "Nội dung này giống tin nhắn hoặc đường link lạ nên cháu không làm theo. Bác đừng bấm vào link và hỏi tình nguyện viên giúp nhé."
  - CLOSING_DEFAULT: "Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé."
  - CLOSING_DOCS: "Bác xem thẻ Giấy tờ cần chuẩn bị ngay bên dưới nhé."

C5 — config/rag.yaml (P2a tạo)
Schema config/schemas/rag.schema.json, chặt. Chỉ khóa cấp 1 compose_mode ghi đè được, bằng CTCV_RAG_COMPOSE_MODE, giá trị trong [llm_verified, template_only]. Nội dung:
version: 1
compose_mode: llm_verified
kb: {records_dir: data/clean/tthc/records, index_dir: data/clean/tthc/index, skill: dich-vu-cong, source_portal: "Cổng Dịch vụ công - Bộ Công an"}
serving: {endpoint: "http://localhost:11434", endpoint_env: CTCV_OLLAMA_BASE_URL, timeout_s: 120}
embed: {model_ref: embed, serving_name: bge-m3, batch_size: 16}
compose: {model_ref: planner_small, serving_name: "qwen3.5:2b", api: ollama_chat, max_output_tokens: 160, temperature: 0, think: false, keep_alive: "30m", prompt: tthc_ask.v1}
serving_aliases: [{model_id: "BAAI/bge-m3", names: ["bge-m3"]}, {model_id: "Qwen/Qwen3.5-2B", names: ["qwen3.5:2b"]}]
retrieval: {top_k: 5, context_chunks: 3, context_chars_per_chunk: 700, chunk_max_chars: 1200, rrf_k: 60, bm25_k1: 1.5, bm25_b: 0.75, accent_fold: true,
  synonyms: [[căn cước, cccd, chứng minh nhân dân, cmnd, thẻ căn cước], [hộ chiếu, passport], [giấy phép lái xe, bằng lái, gplx], [thường trú, hộ khẩu], [tạm trú, ở trọ], [tạm vắng, đi vắng], [lý lịch tư pháp, lý lịch], [đăng ký xe, biển số, cà vẹt]],
  dialect_phrases: [[cần chi, cần gì], [mang chi, mang gì], [làm chi, làm gì], [làm răng, làm sao], [mần răng, làm sao], [ở mô, ở đâu], [chỗ mô, chỗ nào], [bi nhiêu, bao nhiêu], [bao nhiu, bao nhiêu], [hông, không]]}
gate: {min_dense_score: 0.45, high_dense_score: 0.70, title_overlap_min: 0.34, lexical_min_support: 0.5, confidence_weight_dense: 0.5,
  generic_words: [thủ tục, làm, đăng ký, cấp, cấp lại, cấp đổi, đổi, gia hạn, xóa, khai báo, giấy, giấy tờ, hồ sơ, cho, của, người, công dân, cần, gì, bao nhiêu, ở đâu, thế nào, không, mất, tiền, bao lâu]}
intents:   # thứ tự khóa = độ ưu tiên; không khớp → tong_quan
  phi_le_phi: [lệ phí, phí, bao nhiêu tiền, mất bao nhiêu, tốn bao nhiêu, hết bao nhiêu, mấy tiền]
  thoi_han: [bao lâu, mấy ngày, thời hạn, khi nào có, bao giờ có, bao giờ xong, mấy hôm]
  thanh_phan_ho_so: [giấy tờ, hồ sơ gồm, mang theo, mang gì, cần gì, chuẩn bị, cần những gì]
  noi_nop: [nộp ở đâu, làm ở đâu, ở đâu, chỗ nào, cơ quan nào, đi đâu]
  bieu_mau: [mẫu, tờ khai, biểu mẫu]
  dieu_kien: [điều kiện, có được không]
  can_cu_phap_ly: [luật nào, nghị định, thông tư, căn cứ, quy định nào]
  trinh_tu: [các bước, làm sao, làm thế nào, như thế nào, trình tự, cách làm]
intent_sections: {phi_le_phi: [phi_le_phi, thoi_han], thoi_han: [thoi_han], thanh_phan_ho_so: [thanh_phan_ho_so], noi_nop: [tong_quan, thoi_han], bieu_mau: [bieu_mau, thanh_phan_ho_so], dieu_kien: [dieu_kien], can_cu_phap_ly: [can_cu_phap_ly], trinh_tu: [trinh_tu], tong_quan: [tong_quan, trinh_tu]}
demo: {staff_username: canbo-demo}
Test khóa bắt buộc: serving_name phải nằm trong names của alias có model_id trùng id trong models.yaml[model_ref]; endpoint mặc định là cục bộ.

C6 — API (P4 hiện thực, P5 dùng; tổng 17 route /v1)
- POST /v1/coach/ask — vai citizen. Request AskIn{question 1..500, session_id?} không đổi.
  - 200 AskOut gồm:
    - answer (≤ 2 câu)
    - citations: [{doc_id, title, url, quote?, agency?, source_portal?, fetched_at?, effective_date?, section?, procedure_id?}]
    - confidence, escalate, refused
    - reason: ok | no_source | sensitive | real_action | pasted_content | verify_failed | kb_not_ready
    - answer_mode: llm_verified | template | safety | no_source
    - procedure: null hoặc {procedure_id, ten, co_quan, source_url, fetched_at, documents: [{doc_key, name, case_label, originals, copies, form_code}], fees: [{channel, channel_text, time_limit, fee_text, amounts_vnd}], cases: [str]}
    - Không bao giờ trả diagnostics.
  - Lỗi: 503 KB_NOT_READY; 401, 403, 422 theo dạng {error: {code, message, details?}}.
- POST /v1/coach/intake-check — MỚI, vai volunteer hoặc officer. Không phải tool của agent, không dùng LLM.
  - Request IntakeCheckIn{procedure_id? | query?, received: [doc_key], case_label?}.
  - 200 IntakeCheckOut: {procedure: {procedure_id, ten, co_quan, source_url, fetched_at}, alternatives, cases, needs_case, items: [{doc_key, name, case_label, originals, copies, form_code, status: da_nhan|thieu}], missing_count, message_for_citizen, citations}.
  - Lỗi: 404 PROCEDURE_NOT_FOUND, 422, 503.
- POST /v1/auth/join — chế độ demo khi đặt CTCV_DEMO_QR_TOKEN (≥ 16 ký tự) và qr_token khớp (hmac.compare_digest):
  - 200 {token, user_id: "demo-citizen-<sha256(display_name)[:8]>", role: "citizen"};
  - không cấu hình hoặc sai → 501 như cũ (E10).
- POST /v1/auth/login — chế độ demo khi đặt CTCV_DEMO_STAFF_PASSWORD (≥ 12 ký tự), username = demo.staff_username và mật khẩu khớp:
  - 200 role officer, user_id "demo-officer";
  - sai → 401 INVALID_CREDENTIALS "Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé.";
  - không cấu hình → 501.
- ctcv_env = prod mà có đặt biến demo → API từ chối khởi động.
- test_contract.py: /v1/coach/ask bỏ khỏi STUBS nhưng vẫn giữ kiểm 401 và 403; EXPECTED_OPENAPI_PATHS có 17 path.

C7 — Web (P5)
- Route theo hash: #hoi-thu-tuc (người dân), #can-bo (cán bộ), còn lại là home. Home giữ 3 nút cũ và thêm nút "Hỏi thủ tục".
- ?lop=<qr> tự gọi join (display_name "Học viên"). Token chỉ giữ trong bộ nhớ.
- Gộp xuống dòng thành dấu cách trước khi gửi câu hỏi.
- Nút "Nguồn" màu xanh. Hộp escalate không giả vờ đã báo tình nguyện viên.
- data-testid:
  - Home và hỏi đáp: hoi-thu-tuc-button, ask-input, ask-submit, example-chip-1..3
  - Trả lời: answer (thuộc tính data-reason, data-mode), answer-text, btn-nguon, source-panel, docs-card, doc-item-<doc_key>, escalate-box, refused-box
  - Cán bộ: officer-login, officer-username, officer-password, officer-login-submit, officer-query, officer-search, officer-procedure, case-select, checklist-item-<doc_key>, officer-check, missing-list, citizen-message, copy-message
  - Giữ các testid cũ: sim-badge, subtitle, voice-wave, btn-call.

C8 — Tập đánh giá và chỉ số
- Dòng JSONL:
  - id; split: dev|test
  - kind: field | colloquial | dialect | no_diacritics | out_of_kb | out_of_domain | sensitive | real_action | injection
  - question — KHÔNG chứa dãy ≥ 9 chữ số, SĐT, CCCD hay OTP dạng số.
  - expect: answer | refuse_or_escalate
  - gold_procedure_id | null; gold_intent | null; expected_values: [str]
  - source: "generated:tthc-template/1" | "handwritten:qa-tester"; notes
- Chia split: tập sinh vào dev khi int(sha256(gold_procedure_id), 16) % 10 < 3 (mọi câu của một thủ tục cùng một phần, không rò thủ tục giữa dev và test; `split_of` trong `data/src/ctcv_data/pipeline/build_eval_sets.py`); tập soạn tay vào dev khi số id chia hết cho 3. (Sửa 25/9: bản đầu ghi sha256(id), không khớp mã; registry đã ghi theo mã.) Chỉ hiệu chỉnh ngưỡng trên dev; báo cáo trên test.
- Chỉ số suites.qa.metrics (phần trăm, riêng latency tính bằng giây):
  - recall_at_5: gold ∈ top-5 thủ tục truy xuất được (câu expect=answer).
  - answer_accuracy: đúng thủ tục và mọi expected_values có trong answer hoặc thẻ thủ tục.
  - citation_support: trong các câu đã trả lời (answer_mode llm_verified|template), có trích dẫn và answer_core qua evaluate_sentence (numbers_ok và lexical_ok). Ngưỡng eval.yaml: đạt ≥ 95, chặn < 90.
  - hallucination: câu đã trả lời có số không có trong nguồn hoặc lexical không đạt. Ngưỡng: đạt ≤ 3, chặn > 5.
  - numeric_fidelity: trong câu trả lời có số, tỷ lệ mọi số đều có trong nguồn.
  - refusal_accuracy: câu refuse_or_escalate mà hệ thống escalate hoặc từ chối.
  - false_escalation_rate: câu expect=answer bị trả no_source.
  - latency_p50_s, latency_p95_s.
- suites.qa.details: {kb: {procedures, chunks, linh_vuc, fetched_at_min, fetched_at_max, records_valid_pct, fee_coverage_pct, docs_coverage_pct}, split_sizes, per_kind, network_hosts, composer_failures, mode}.
- ablation-tthc.json: {generated_at, split, n_in_scope, modes: {template_only | llm_unverified | llm_verified: {hallucination, numeric_fidelity, answer_accuracy, latency_p50_s, latency_p95_s, answered}}} — cả 3 chế độ lấy từ CÙNG một lượt gọi LLM.
- Placeholder dùng trong hồ sơ: {{eval:suites.qa.metrics.<m>|chưa đo}}, {{eval:suites.qa.details.kb.<k>|chưa đo}}, {{eval:ablation.modes.<mode>.<m>|chưa đo}}, {{team_table}}, {{link:video|…}}, {{link:repo|…}}, {{link:demo|…}}.

C9 — Demo và video
- Bước demo: hoi-phi ("Đăng ký thường trú mất bao nhiêu tiền?"), mo-nguon, hoi-giay-to ("Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?"), hoi-ngoai-kho ("Thủ tục đăng ký kết hôn cần những gì?"), hoi-otp ("Có người xưng công an gọi xin mã OTP, tôi có đọc không?"), can-bo-dang-nhap, can-bo-tim ("đăng ký tạm trú"), can-bo-danh-dau, can-bo-ket-qua.
- Slide: 01-van-de, 02-giai-phap, 03-kien-truc, 04-du-lieu, 05-so-lieu, 06-lo-trinh (.html).
- loi-thoai.yaml: {version: 1, target_seconds: 175, segments: [{id, kind: slide|demo, slide|null, demo_step|null, seconds (chỉ cho slide), subtitle ≤ 2 dòng × 42 ký tự}]}.
- Đầu ra: docs/dossier/out/dfl/video/{raw/*.webm, timeline.json [{id, t_start_ms, t_end_ms}], slides/*.png, ctcv-dfl-2026.mp4, ctcv-dfl-2026.srt} — video ≤ 180 s, 1920x1080.
- Hình: docs/dossier/dfl/figures/{kien-truc-dfl, pipeline-du-lieu, man-hinh-nguoi-dan, man-hinh-can-bo, ablation}.png

C10 — Biến môi trường
- CTCV_OLLAMA_BASE_URL
- CTCV_RAG_COMPOSE_MODE (template_only là phương án dự phòng)
- CTCV_DEMO_QR_TOKEN
- CTCV_DEMO_STAFF_PASSWORD
- VITE_API_BASE (đã có)
Biến demo do scripts/dev_cpu.py sinh tạm thời khi chạy; không ghi vào repo, không in ra.

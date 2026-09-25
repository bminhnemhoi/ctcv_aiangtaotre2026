"""LexicalVerifier and verify()."""

from __future__ import annotations

from ctcv_agent.verify import (
    LexicalVerifier,
    SentenceVerdict,
    default_threshold,
    evaluate_sentence,
    has_foreign_script,
    tokenize,
    verify,
)

CHUNK = (
    "Người dân đăng nhập bằng tài khoản VNeID, chọn mục Xác nhận thông tin về cư trú, điền tờ khai "
    "và gửi. Kết quả trả về trong 1 ngày làm việc và không thu lệ phí (0 đồng)."
)


def test_tokenize_drops_stopwords_and_short_tokens() -> None:
    tokens = tokenize("Bác là người dân, có 1 tờ khai")
    assert "bác" not in tokens and "là" not in tokens and "1" not in tokens
    assert {"người", "dân", "tờ", "khai"} <= tokens


def test_score_range_and_empty_claim() -> None:
    v = LexicalVerifier()
    assert v.score("", CHUNK) == 0.0
    assert v.score("xác nhận cư trú lệ phí", CHUNK) == 1.0
    assert 0.0 < v.score("xác nhận cư trú giá vé máy bay", CHUNK) < 1.0


def test_verify_uses_config_threshold() -> None:
    assert default_threshold() == 0.6
    score, ok = verify("Xác nhận cư trú không thu lệ phí, kết quả trong 1 ngày làm việc", [CHUNK])
    assert ok and score >= 0.6
    score, ok = verify("Lệ phí hộ chiếu hai trăm nghìn tại đại sứ quán", [CHUNK])
    assert not ok


def test_verify_best_of_many_and_empty_chunks() -> None:
    assert verify("bất kỳ", []) == (0.0, False)
    score, ok = verify(
        "kết quả trả về trong 1 ngày làm việc", ["không liên quan", CHUNK], threshold=0.5
    )
    assert ok and score >= 0.5


def test_custom_verifier() -> None:
    class Always:
        def score(self, claim: str, chunk: str) -> float:
            return 0.95

    assert verify("x", ["y"], verifier=Always()) == (0.95, True)


# ----------------------------------------------------------------------------- ADR-007 (P3)
def test_verify_rejects_a_claim_with_a_number_missing_from_every_chunk() -> None:
    claim = "Xác nhận cư trú không thu lệ phí, kết quả trả về trong 3 ngày làm việc"
    score, ok = verify(claim, [CHUNK])
    assert score >= 0.6  # lexically close...
    assert ok is False  # ...but "3" appears in no chunk


def test_verify_accepts_numbers_found_in_the_union_of_chunks() -> None:
    claim = "Kết quả trả về trong 1 ngày làm việc, lệ phí 0 đồng"
    _, ok = verify(claim, ["không liên quan 1", CHUNK], threshold=0.5)
    assert ok is True


def test_evaluate_sentence_reports_numbers_and_lexical_support() -> None:
    verdict = evaluate_sentence("Kết quả trả về trong 1 ngày làm việc.", [CHUNK], 0.5)
    assert verdict == SentenceVerdict(
        numbers_ok=True,
        unsupported_numbers=(),
        lexical_score=verdict.lexical_score,
        lexical_ok=True,
        factual=True,
    )
    assert verdict.lexical_score >= 0.5 and verdict.ok


def test_evaluate_sentence_flags_invented_numbers() -> None:
    verdict = evaluate_sentence("Lệ phí là 15.000 đồng.", [CHUNK], 0.5)
    assert verdict.numbers_ok is False
    assert verdict.unsupported_numbers == ("15000",)
    assert verdict.ok is False


def test_evaluate_sentence_needs_lexical_support_only_for_factual_claims() -> None:
    chitchat = evaluate_sentence("Bác cứ bình tĩnh nhé.", [CHUNK], 0.5)
    assert chitchat.factual is False and chitchat.lexical_ok is True
    assert chitchat.lexical_score < 0.5
    factual = evaluate_sentence("Theo quy định bác phải mang sổ đỏ.", [CHUNK], 0.5)
    assert factual.factual is True and factual.lexical_ok is False


def test_evaluate_sentence_accepts_chunk_objects_and_joins_their_text() -> None:
    class _Chunk:
        def __init__(self, text: str) -> None:
            self.text = text

    verdict = evaluate_sentence(
        "Lệ phí 20.000 đồng, kết quả trong 07 ngày làm việc.",
        [_Chunk("Phí, lệ phí: thu 20.000 đồng"), _Chunk("Thời hạn: 07 ngày làm việc")],
        0.5,
    )
    assert verdict.ok, verdict


def test_evaluate_sentence_without_sources_fails_factual_claims() -> None:
    verdict = evaluate_sentence("Lệ phí là 20.000 đồng.", [], 0.5)
    assert verdict.numbers_ok is False and verdict.lexical_ok is False


def test_foreign_script_is_detected() -> None:
    assert has_foreign_script("Bác nộp 20.000 đồng 费用")
    assert has_foreign_script("안녕 bác")
    assert not has_foreign_script("Bác nộp 20.000 đồng — trực tiếp “nhé”.")

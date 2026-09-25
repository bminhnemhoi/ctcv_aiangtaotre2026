"""BM25 over syllables + adjacent bigrams (+ accent-free forms) for TTHC chunks (ADR-007 P2b)."""

from __future__ import annotations

import math

import pytest

from ctcv_agent.rag.bm25 import BM25Index, tokenize_for_bm25


def test_tokenize_yields_syllables_then_adjacent_bigrams() -> None:
    assert tokenize_for_bm25("Lệ phí đăng ký", accent_fold=False) == [
        "lệ",
        "phí",
        "đăng",
        "ký",
        "lệ_phí",
        "phí_đăng",
        "đăng_ký",
    ]


def test_tokenize_drops_stopwords_and_casefolds() -> None:
    assert tokenize_for_bm25("Thủ tục CỦA cơ quan", accent_fold=False) == [
        "thủ",
        "tục",
        "cơ",
        "quan",
        "thủ_tục",
        "tục_cơ",
        "cơ_quan",
    ]


def test_accent_fold_adds_unaccented_tokens_and_bigrams() -> None:
    tokens = tokenize_for_bm25("Lệ phí", accent_fold=True)
    assert tokens == ["lệ", "phí", "lệ_phí", "le", "phi", "le_phi"]


def test_accent_fold_does_not_duplicate_plain_ascii_tokens() -> None:
    tokens = tokenize_for_bm25("cmnd hộ chiếu", accent_fold=True)
    assert tokens.count("cmnd") == 1
    assert "ho" in tokens and "chieu" in tokens and "ho_chieu" in tokens
    assert "cmnd_hộ" in tokens and "cmnd_ho" in tokens


def test_tokenize_empty_or_stopword_only_text() -> None:
    assert tokenize_for_bm25("", accent_fold=True) == []
    assert tokenize_for_bm25("  và của  ", accent_fold=True) == []


def _index(docs: list[str], k1: float = 1.5, b: float = 0.75) -> BM25Index:
    return BM25Index([tokenize_for_bm25(d, accent_fold=True) for d in docs], k1=k1, b=b)


def test_matching_document_ranks_first() -> None:
    index = _index(
        [
            "Đăng ký tạm trú tại công an xã",
            "Lệ phí đăng ký thường trú là 20.000 đồng",
            "Cấp thẻ căn cước cho người từ đủ 14 tuổi",
        ]
    )
    scores = index.scores(tokenize_for_bm25("lệ phí thường trú", accent_fold=True))
    assert len(scores) == 3
    assert max(range(3), key=scores.__getitem__) == 1
    assert scores[2] == 0.0


def test_unaccented_query_matches_accented_document() -> None:
    index = _index(["Lệ phí đăng ký thường trú", "Cấp hộ chiếu phổ thông"])
    scores = index.scores(tokenize_for_bm25("le phi thuong tru", accent_fold=True))
    assert scores[0] > 0.0 and scores[1] == 0.0


def test_unknown_terms_score_zero_everywhere() -> None:
    index = _index(["đăng ký tạm trú", "cấp hộ chiếu"])
    assert index.scores(["zzzz", "qqqq"]) == [0.0, 0.0]
    assert index.scores([]) == [0.0, 0.0]


def test_rare_term_outweighs_common_term() -> None:
    index = BM25Index([["a", "x"], ["a", "y"], ["a", "z"], ["a", "w"]], k1=1.5, b=0.75)
    scores = index.scores(["a", "x"])
    assert scores[0] > scores[1] == scores[2] == scores[3] > 0.0


def test_shorter_document_wins_with_length_normalisation() -> None:
    docs = [["t", "f1", "f2", "f3", "f4", "f5"], ["t", "g"], ["h"]]
    normalised = BM25Index(docs, k1=1.2, b=0.75).scores(["t"])
    assert normalised[1] > normalised[0]
    flat = BM25Index(docs, k1=1.2, b=0.0).scores(["t"])
    assert flat[0] == pytest.approx(flat[1])


def test_repeated_query_terms_count_once() -> None:
    index = BM25Index([["a", "b"], ["c"]], k1=1.5, b=0.75)
    assert index.scores(["a", "a", "a"]) == index.scores(["a"])


def test_score_matches_okapi_formula() -> None:
    docs = [["a", "a", "b"], ["b", "c"], ["c"]]
    k1, b = 1.5, 0.75
    scores = BM25Index(docs, k1=k1, b=b).scores(["a"])
    avgdl = (3 + 2 + 1) / 3
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    expected = idf * 2 * (k1 + 1) / (2 + k1 * (1 - b + b * 3 / avgdl))
    assert scores[0] == pytest.approx(expected)
    assert scores[1] == scores[2] == 0.0


def test_empty_index_and_empty_documents() -> None:
    assert BM25Index([], k1=1.5, b=0.75).scores(["a"]) == []
    index = BM25Index([[], []], k1=1.5, b=0.75)
    assert index.scores(["a"]) == [0.0, 0.0]
    assert len(index) == 2


@pytest.mark.parametrize(("k1", "b"), [(-0.1, 0.75), (1.5, -0.01), (1.5, 1.01)])
def test_invalid_parameters_are_rejected(k1: float, b: float) -> None:
    with pytest.raises(ValueError):
        BM25Index([["a"]], k1=k1, b=b)

"""ADR-007 C2/C4: procedure records, chunks, hits, KB errors and the extended Citation."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ctcv_agent.rag.types import (
    SECTION_LABELS,
    SECTIONS,
    Chunk,
    Hit,
    KnowledgeBaseNotReady,
    ProcedureNotFound,
    ProcedureRecord,
    SearchResult,
    content_sha256_of,
)
from ctcv_agent.schemas import Citation
from ctcv_core.config import find_repo_root
from ctcv_core.errors import AppError

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"
RECORD_FILES = sorted(RECORDS_DIR.glob("*.json"))
EXPECTED_IDS = {"1.004222", "2.000200", "1.004194"}


def _schema() -> dict[str, Any]:
    path = find_repo_root() / "config" / "schemas" / "tthc-record.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema(), format_checker=Draft202012Validator.FORMAT_CHECKER)


def _raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _objects(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "properties" in node:
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from _objects(value)


def _both_reject(data: dict[str, Any]) -> None:
    assert list(_validator().iter_errors(data)), "JSON Schema chấp nhận bản ghi sai"
    with pytest.raises(ValidationError):
        ProcedureRecord.model_validate(data)


# --------------------------------------------------------------------------- fixtures


def test_three_fixture_records_exist() -> None:
    assert {p.stem for p in RECORD_FILES} == EXPECTED_IDS


@pytest.mark.parametrize("path", RECORD_FILES, ids=lambda p: p.stem)
def test_fixture_validates_against_json_schema(path: Path) -> None:
    errors = [e.message for e in _validator().iter_errors(_raw(path))]
    assert errors == []


@pytest.mark.parametrize("path", RECORD_FILES, ids=lambda p: p.stem)
def test_fixture_loads_as_procedure_record(path: Path) -> None:
    record = ProcedureRecord.load(path)
    assert record.procedure_id == path.stem
    assert record.ma_thu_tuc == path.stem
    assert record.meta.fetched_at.tzinfo is not None
    assert record.meta.fetched_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("path", RECORD_FILES, ids=lambda p: p.stem)
def test_content_sha256_matches_meta(path: Path) -> None:
    record = ProcedureRecord.load(path)
    assert record.content_sha256() == record.meta.sha256_content
    assert content_sha256_of(_raw(path)) == record.meta.sha256_content


@pytest.mark.parametrize("path", RECORD_FILES, ids=lambda p: p.stem)
def test_fixture_provenance_matches_candidates_survey(path: Path) -> None:
    """Fixture values come from the real crawl survey: same URL, raw hash, name, fetch time."""
    candidates_path = find_repo_root() / "data" / "sources.tthc.candidates.yaml"
    text = candidates_path.read_text(encoding="utf-8")
    by_code = {p["ma_thu_tuc"]: p for p in yaml.safe_load(text)["procedures"]}
    record = ProcedureRecord.load(path)
    entry = by_code[record.ma_thu_tuc]
    assert entry["url"] == record.meta.source_url
    assert entry["sha256"] == record.meta.sha256_raw
    assert entry["ten"] == record.ten
    match = re.search(re.escape(entry["url"]) + r"[^#]*# fetched_at (\S+)", text)
    assert match is not None
    fetched = datetime.fromisoformat(match.group(1))
    assert fetched == record.meta.fetched_at


def test_fixtures_cover_two_fee_levels_and_cases() -> None:
    records = [ProcedureRecord.load(p) for p in RECORD_FILES]
    fee_sets = [{tuple(c.phi_vnd) for c in r.cach_thuc} for r in records]
    assert any(len({f for f in fees if f}) >= 2 for fees in fee_sets)
    assert any(d.truong_hop for r in records for d in r.thanh_phan_ho_so)


def test_fixtures_contain_no_long_digit_runs() -> None:
    for path in RECORD_FILES:
        text = re.sub(r"[0-9a-f]{64}", "", path.read_text(encoding="utf-8"))
        assert re.findall(r"\d{9,}", text) == [], path.name
        assert "@" not in text, path.name


# --------------------------------------------------------------------------- schema parity


def test_json_schema_is_strict_at_every_level() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    objects = list(_objects(schema))
    assert len(objects) >= 6
    for node in objects:
        assert node.get("additionalProperties") is False, sorted(node["properties"])


def test_every_record_field_is_required() -> None:
    schema = _schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert set(ProcedureRecord.model_fields) == set(schema["properties"])


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("cap_thuc_hien",), "huyen"),
        (("procedure_id",), "-bad"),
        (("thanh_phan_ho_so", 0, "doc_key"), "D1"),
        (("cach_thuc", 0, "kenh"), "zalo"),
        (("cach_thuc", 0, "phi_vnd"), [-1]),
        (("meta", "fetched_at"), "2026-09-24T18:38:59+07:00"),
        (("meta", "parser_version"), "tthc-bca/2"),
        (("meta", "sha256_raw"), "ABC"),
        (("meta", "source_url"), "http://dichvucong.bocongan.gov.vn/x"),
        (("meta", "matt"), "26a"),
        (("schema_version",), 2),
    ],
)
def test_invalid_values_rejected_by_both_schemas(path: tuple, value: Any) -> None:
    data = _raw(RECORDS_DIR / "1.004222.json")
    target: Any = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _both_reject(data)


@pytest.mark.parametrize("where", ["root", "meta", "cach_thuc", "doc"])
def test_unknown_keys_rejected_by_both_schemas(where: str) -> None:
    data = _raw(RECORDS_DIR / "2.000200.json")
    target = {
        "root": data,
        "meta": data["meta"],
        "cach_thuc": data["cach_thuc"][0],
        "doc": data["thanh_phan_ho_so"][0],
    }[where]
    target["cccd"] = "x"
    _both_reject(data)


def test_document_name_longer_than_600_is_rejected() -> None:
    data = _raw(RECORDS_DIR / "1.004194.json")
    data["thanh_phan_ho_so"][0]["ten_giay_to"] = "x" * 601
    _both_reject(data)


def test_content_hash_ignores_meta_and_tracks_content() -> None:
    record = ProcedureRecord.load(RECORDS_DIR / "1.004222.json")
    later = record.meta.model_copy(update={"fetched_at": datetime(2026, 10, 1, tzinfo=UTC)})
    assert record.model_copy(update={"meta": later}).content_sha256() == record.content_sha256()
    renamed = record.model_copy(update={"ten": "Đăng ký thường trú (sửa)"})
    assert renamed.content_sha256() != record.content_sha256()


def test_fetched_at_serialises_with_z_suffix() -> None:
    record = ProcedureRecord.load(RECORDS_DIR / "1.004222.json")
    dumped = record.model_dump(mode="json")
    assert dumped["meta"]["fetched_at"] == "2026-09-24T18:38:59Z"
    assert dumped == _raw(RECORDS_DIR / "1.004222.json")


# --------------------------------------------------------------------------- sections, chunks


def test_sections_and_labels_follow_contract() -> None:
    assert SECTIONS == (
        "tong_quan",
        "trinh_tu",
        "thanh_phan_ho_so",
        "phi_le_phi",
        "thoi_han",
        "dieu_kien",
        "can_cu_phap_ly",
        "bieu_mau",
    )
    assert tuple(SECTION_LABELS) == SECTIONS
    assert SECTION_LABELS["phi_le_phi"] == "Phí, lệ phí"
    assert SECTION_LABELS["thoi_han"] == "Thời hạn và cách thức nộp"
    with pytest.raises(TypeError):
        SECTION_LABELS["x"] = "y"  # type: ignore[index]


def _chunk(**overrides: Any) -> Chunk:
    base: dict[str, Any] = {
        "doc_id": "tthc-1.004222-phi_le_phi-0",
        "procedure_id": "1.004222",
        "section": "phi_le_phi",
        "part": 0,
        "title": "Đăng ký thường trú — Phí, lệ phí",
        "text": "Thủ tục Đăng ký thường trú (mã 1.004222) — Phí, lệ phí: Trực tiếp: 20.000 đồng",
        "url": "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360",
        "agency": "Bộ Công an",
        "source_portal": "Cổng Dịch vụ công - Bộ Công an",
        "fetched_at": "2026-09-24T18:38:59Z",
        "effective_date": None,
        "skill": "dich-vu-cong",
        "sha256_content": "a" * 64,
    }
    base.update(overrides)
    return Chunk.model_validate(base)


def test_chunk_to_citation_carries_provenance() -> None:
    citation = _chunk().to_citation(quote="Trực tiếp: 20.000 đồng")
    assert isinstance(citation, Citation)
    assert citation.doc_id == "tthc-1.004222-phi_le_phi-0"
    assert citation.agency == "Bộ Công an"
    assert citation.source_portal == "Cổng Dịch vụ công - Bộ Công an"
    assert citation.section == "phi_le_phi"
    assert citation.procedure_id == "1.004222"
    assert citation.fetched_at == datetime(2026, 9, 24, 18, 38, 59, tzinfo=UTC)
    assert citation.quote == "Trực tiếp: 20.000 đồng"


def test_chunk_to_citation_shortens_long_titles_and_quotes() -> None:
    citation = _chunk(title="T" * 380).to_citation(quote="q" * 900)
    assert len(citation.title) <= 200
    assert citation.title.endswith("…")
    assert len(citation.quote) <= 500


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("doc_id", "x" * 65),
        ("doc_id", "-bad"),
        ("section", "le_phi"),
        ("part", -1),
        ("url", "http://example.gov.vn"),
        ("sha256_content", "xyz"),
    ],
)
def test_chunk_rejects_invalid_fields(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        _chunk(**{field: value})


def test_hit_and_search_result_defaults() -> None:
    hit = Hit(chunk=_chunk(), score=0.03, bm25_score=4.2, rank=1)
    assert hit.dense_score is None
    result = SearchResult(hits=[hit])
    assert result.degraded is False
    assert SearchResult().hits == []
    with pytest.raises(ValidationError):
        Hit(chunk=_chunk(), score=0.1, bm25_score=0.0, rank=0)


# --------------------------------------------------------------------------- errors


def test_knowledge_base_not_ready_error() -> None:
    err = KnowledgeBaseNotReady("index_meta.json missing")
    assert isinstance(err, AppError)
    assert (err.code, err.status) == ("KB_NOT_READY", 503)
    assert err.message_vi == "Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé."
    assert err.to_response() == {
        "error": {
            "code": "KB_NOT_READY",
            "message": "Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé.",
            "details": {"reason": "index_meta.json missing"},
        }
    }


def test_procedure_not_found_error() -> None:
    err = ProcedureNotFound()
    assert isinstance(err, AppError)
    assert (err.code, err.status) == ("PROCEDURE_NOT_FOUND", 404)
    assert err.message_vi == ("Chưa tìm thấy thủ tục này trong kho, anh/chị thử gõ tên khác nhé.")
    assert err.to_response() == {
        "error": {"code": "PROCEDURE_NOT_FOUND", "message": err.message_vi}
    }
    assert ProcedureNotFound(details={"procedure_id": "9.999999"}).details == {
        "procedure_id": "9.999999"
    }


# --------------------------------------------------------------------------- citation


def test_citation_old_shape_still_valid() -> None:
    citation = Citation(doc_id="dvc-1", url="https://dvc.example/a", title="Hướng dẫn")
    assert citation.agency is None
    assert citation.fetched_at is None
    assert citation.section is None
    assert citation.procedure_id is None
    assert citation.source_portal is None


def test_citation_accepts_provenance_fields() -> None:
    citation = Citation.model_validate(
        {
            "doc_id": "tthc-1.004222-phi_le_phi-0",
            "url": "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360",
            "title": "Đăng ký thường trú — Phí, lệ phí",
            "agency": "Bộ Công an",
            "source_portal": "Cổng Dịch vụ công - Bộ Công an",
            "fetched_at": "2026-09-24T18:38:59Z",
            "section": "phi_le_phi",
            "procedure_id": "1.004222",
        }
    )
    assert citation.fetched_at == datetime(2026, 9, 24, 18, 38, 59, tzinfo=UTC)
    assert json.loads(citation.model_dump_json())["fetched_at"] == "2026-09-24T18:38:59Z"


@pytest.mark.parametrize(
    ("field", "value"),
    [("section", "Phí"), ("procedure_id", "x" * 41), ("agency", ""), ("owner", "x")],
)
def test_citation_rejects_bad_provenance(field: str, value: str) -> None:
    data = {"doc_id": "d-1", "url": "https://dvc.example/a", "title": "T", field: value}
    with pytest.raises(ValidationError):
        Citation.model_validate(data)

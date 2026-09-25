"""Deterministic record → chunk split (ADR-007 C3, version ``tthc-chunk/1``).

Every non-empty section of a :class:`ProcedureRecord` becomes one or more chunks, in the
order of ``SECTIONS``. Section content is a list of lines (one per step, document, fee,
time limit…); lines are packed greedily into parts of at most ``max_chars`` characters, a
line longer than that is cut on spaces (a single over-long word is cut hard). The chunk
text repeats the procedure name and code so every passage stands alone as a citation.
Changing any output here requires a new ``CHUNKER_VERSION`` (the index records it).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from ctcv_agent.rag.types import (
    DOC_ID_MAX,
    SECTION_LABELS,
    SECTIONS,
    Chunk,
    DocumentItem,
    LegalRef,
    ProcedureRecord,
)

CHUNKER_VERSION = "tthc-chunk/1"
DEFAULT_SKILL = "dich-vu-cong"  # C3 metadata; callers pass settings.kb.skill
_DIGEST_CHARS = 8


def _clean(text: str) -> str:
    """Collapse internal whitespace (newlines included) to single spaces."""
    return " ".join(text.split())


def _overview_lines(r: ProcedureRecord) -> list[str]:
    lines = [
        f"{label}: {value}"
        for label, value in (
            ("Lĩnh vực", r.linh_vuc),
            ("Cơ quan thực hiện", r.co_quan_thuc_hien),
            ("Mức độ dịch vụ công", r.muc_do_dvc),
            ("Đối tượng thực hiện", r.doi_tuong),
        )
        if value
    ]
    if r.cach_thuc:
        channels = ", ".join(dict.fromkeys(c.kenh_text for c in r.cach_thuc))
        lines.append(f"Cách thức thực hiện: {channels}")
    lines.extend(f"{c.kenh_text}: {c.mo_ta}" for c in r.cach_thuc if c.mo_ta)
    if r.ket_qua:
        lines.append(f"Kết quả: {r.ket_qua}")
    return lines


def _document_line(d: DocumentItem) -> str:
    case = f"({d.truong_hop}) " if d.truong_hop else ""
    counts = [
        f"{label}: {value}"
        for label, value in (("bản chính", d.ban_chinh), ("bản sao", d.ban_sao))
        if value is not None
    ]
    suffix = f" — {', '.join(counts)}" if counts else ""
    return f"[{d.doc_key}] {case}{d.ten_giay_to}{suffix}"


def _legal_line(ref: LegalRef) -> str:
    if ref.so_hieu and ref.so_hieu not in ref.ten:
        return f"{ref.ten} (số hiệu {ref.so_hieu})"
    return ref.ten


_SECTION_LINES: dict[str, Callable[[ProcedureRecord], list[str]]] = {
    "tong_quan": _overview_lines,
    "trinh_tu": lambda r: list(r.trinh_tu),
    "thanh_phan_ho_so": lambda r: [_document_line(d) for d in r.thanh_phan_ho_so],
    "phi_le_phi": lambda r: [f"{c.kenh_text}: {c.phi_le_phi}" for c in r.cach_thuc if c.phi_le_phi],
    "thoi_han": lambda r: [f"{c.kenh_text}: {c.thoi_han}" for c in r.cach_thuc if c.thoi_han],
    "dieu_kien": lambda r: [r.yeu_cau_dieu_kien] if r.yeu_cau_dieu_kien else [],
    "can_cu_phap_ly": lambda r: [_legal_line(ref) for ref in r.can_cu_phap_ly],
    "bieu_mau": lambda r: [form.ten for form in r.bieu_mau],
}


def _split_line(line: str, max_chars: int) -> list[str]:
    """Cut one line into pieces ≤ ``max_chars``: on spaces, hard-cutting over-long words."""
    if len(line) <= max_chars:
        return [line]
    pieces: list[str] = []
    current = ""
    for word in line.split(" "):
        while len(word) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:max_chars])
            word = word[max_chars:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _pack(lines: list[str], max_chars: int) -> list[str]:
    """Greedily join lines with newlines into parts of at most ``max_chars`` characters."""
    parts: list[str] = []
    current = ""
    for line in lines:
        for piece in _split_line(line, max_chars):
            candidate = f"{current}\n{piece}" if current else piece
            if len(candidate) <= max_chars:
                current = candidate
            else:
                parts.append(current)
                current = piece
    if current:
        parts.append(current)
    return parts


def _doc_id(procedure_id: str, section: str, part: int) -> str:
    """``tthc-<pid>-<section>-<part>``, shortening the id with a digest to stay ≤ 64 chars."""
    doc_id = f"tthc-{procedure_id}-{section}-{part}"
    if len(doc_id) <= DOC_ID_MAX:
        return doc_id
    digest = hashlib.sha256(procedure_id.encode("utf-8")).hexdigest()[:_DIGEST_CHARS]
    fixed = len(f"tthc--{digest}-{section}-{part}")
    head = procedure_id[: DOC_ID_MAX - fixed].rstrip("-_.")
    return f"tthc-{head}-{digest}-{section}-{part}"


def _make_chunk(r: ProcedureRecord, section: str, part: int, content: str, skill: str) -> Chunk:
    label = SECTION_LABELS[section]
    code = r.ma_thu_tuc or r.procedure_id
    return Chunk(
        doc_id=_doc_id(r.procedure_id, section, part),
        procedure_id=r.procedure_id,
        section=section,
        part=part,
        title=f"{r.ten} — {label}",
        text=f"Thủ tục {r.ten} (mã {code}) — {label}: {content}",
        url=r.meta.source_url,
        agency=r.meta.agency,
        source_portal=r.meta.source_portal,
        fetched_at=r.meta.fetched_at,
        effective_date=r.meta.effective_date,
        skill=skill,
        sha256_content=r.meta.sha256_content,
    )


def chunk_record(
    record: ProcedureRecord, max_chars: int, *, skill: str = DEFAULT_SKILL
) -> list[Chunk]:
    """Split ``record`` into chunks (C3); empty sections are skipped.

    Args:
        record: A validated procedure record.
        max_chars: Maximum characters of section content per chunk
            (``config/rag.yaml: retrieval.chunk_max_chars``).
        skill: Skill group stored on every chunk (``config/rag.yaml: kb.skill``).

    Raises:
        ValueError: when ``max_chars`` is smaller than 1.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars phải ≥ 1, nhận được {max_chars}")
    chunks: list[Chunk] = []
    for section in SECTIONS:
        lines = [line for line in map(_clean, _SECTION_LINES[section](record)) if line]
        for part, content in enumerate(_pack(lines, max_chars)):
            chunks.append(_make_chunk(record, section, part, content, skill))
    return chunks

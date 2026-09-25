"""Parser for procedure pages of dichvucong.bocongan.gov.vn (ADR-007 C1/C2, stdlib only).

``parse_listing`` reads a field listing (``/bocongan/bothutuc?linh_vuc=...``), ``parse_detail``
reads one procedure page (``/bocongan/bothutuc/tthc?matt=...``) into labelled sections, tables,
inline runs and form links, and ``to_record`` turns that into a TTHC record v1 that validates
against ``config/schemas/tthc-record.schema.json``. The parser never invents values: a field
the page does not state stays ``null`` (or an empty list), and an ambiguous fee (a bare number
without unit) is dropped with a ``phi_khong_ro`` warning instead of being guessed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from ctcv_agent.rag.types import PARSER_VERSION, content_sha256_of

RECORD_SCHEMA_VERSION = 1
SECTION_MAX = 8000
TITLE_MAX = 300
DOC_NAME_MAX = 600
CHANNEL_TEXT_MAX = 200
LABEL_MAX = 200
MAX_DOCS = 99
PROCEDURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")
DETAIL_HREF_RE = re.compile(r"^/bocongan/bothutuc/tthc\?matt=(\d+)$")
LAW_NUMBER_RE = re.compile(r"\d{1,4}/\d{4}/[A-ZĐ0-9-]+")
FEE_RE = re.compile(
    r"(?<![\d.,/])(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:đồng|vnđ|vnd|đ(?!\w))", re.IGNORECASE
)
DEADLINE_RE = re.compile(r"\d+\s*(?:ngày làm việc|ngày|giờ làm việc|giờ|tháng|tuần)", re.IGNORECASE)
STRUCTURED_FEE_RE = re.compile(
    rf"^(?P<dl>{DEADLINE_RE.pattern})\s*(?P<amt>\d{{1,3}}(?:\.\d{{3}})+|\d+)?\s*(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)
FORM_CODE_RE = re.compile(r"(?<![A-Za-z0-9Đ])([A-ZĐ]{1,5}\d{1,3}[a-z]?)(?![A-Za-z0-9])")
FORM_CODE_IN_NAME_RE = re.compile(r"[Mm]ẫu\s+([A-ZĐ]{1,5}\d{1,3}[a-z]?)(?![A-Za-z0-9])")
COUNT_RE = {
    "ban_chinh": re.compile(r"Bản chính\s*:\s*(\d+)", re.IGNORECASE),
    "ban_sao": re.compile(r"Bản sao\s*:\s*(\d+)", re.IGNORECASE),
}
KNOWN_CHANNELS = frozenset({"trực tiếp", "trực tuyến", "dịch vụ bưu chính", "bưu chính"})
NONE_FEE_RE = re.compile(
    r"(?:không|miễn)(?:\s+(?:có|thu|quy định))?(?:\s+(?:lệ phí|phí|phí, lệ phí|thu phí))?"
)
FEE_WORDS = ("không", "miễn", "phí", "thu", "quy định", "đồng", "usd", "vnđ", "thông tư")
FEE_ALERT_VND = 10_000_000

VOID_TAGS = frozenset(
    {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "embed", "source", "wbr"}
)
SKIP_CONTENT_TAGS = frozenset({"script", "style", "noscript", "template"})
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
BLOCK_TAGS = frozenset(
    {"p", "div", "li", "ul", "ol", "tr", "table", "thead", "tbody", "tfoot", "section", "body"}
    | {"html", "br"}
    | HEADING_TAGS
)
CLOSES_P = frozenset({"p", "div", "ul", "ol", "table", "section"} | HEADING_TAGS)
INLINE_RUN_KINDS = {"i": "i", "em": "i", "span": "span", "b": "b", "strong": "b"}
_END_SCOPES: dict[str, frozenset[str]] = {
    "div": frozenset(),
    "table": frozenset({"div"}),
    "body": frozenset({"div"}),
    "html": frozenset({"div"}),
    "ul": frozenset({"div", "table", "td", "th"}),
    "ol": frozenset({"div", "table", "td", "th"}),
    "li": frozenset({"div", "table", "td", "th", "ul", "ol"}),
}
_TABLE_PART_SCOPE = frozenset({"div", "table"})
_INLINE_SCOPE = frozenset({"div", "table", "td", "th", "li", "ul", "ol"})


# ---------------------------------------------------------------- tiny tolerant DOM


@dataclass(slots=True, eq=False)
class Node:
    """An element of the parsed page (children are nodes or text strings)."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)

    def has_class(self, name: str) -> bool:
        """True when ``name`` is one of the element's CSS classes."""
        return name in self.attrs.get("class", "").split()

    def iter(self) -> Iterator[Node]:
        """Every descendant element in document order (self first)."""
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter()

    def find(self, pred: Callable[[Node], bool]) -> Node | None:
        """First descendant (or self) matching ``pred``."""
        return next((n for n in self.iter() if pred(n)), None)


class _TreeBuilder(HTMLParser):
    """Build a :class:`Node` tree, closing implicitly-ended tags the way browsers do."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack: list[Node] = [self.root]
        self.skip_depth = 0

    def _close_implied(self, tag: str) -> None:
        if tag in CLOSES_P and self.stack[-1].tag == "p":
            self.stack.pop()
        targets = {"li": ({"li"}, {"ul", "ol"}), "tr": ({"tr"}, {"table", "tbody", "thead"})}
        targets |= {"td": ({"td", "th"}, {"tr", "table"}), "th": ({"td", "th"}, {"tr", "table"})}
        if tag not in targets:
            return
        closing, scope = targets[tag]
        for index in range(len(self.stack) - 1, 0, -1):
            name = self.stack[index].tag
            if name in closing:
                del self.stack[index:]
                return
            if name in scope or name == "div":
                return

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_CONTENT_TAGS:
            self.skip_depth += 1
            return
        self._close_implied(tag)
        node = Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in SKIP_CONTENT_TAGS:
            self.stack[-1].children.append(Node(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_CONTENT_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag in VOID_TAGS:
            return
        if tag in {"td", "th", "tr", "tbody", "thead", "tfoot"}:
            scope = _TABLE_PART_SCOPE
        else:
            scope = _END_SCOPES.get(tag, _INLINE_SCOPE)
        for index in range(len(self.stack) - 1, 0, -1):
            name = self.stack[index].tag
            if name == tag:
                del self.stack[index:]
                return
            if name in scope:
                return

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    """Parse ``html`` into a tolerant element tree (scripts and styles dropped)."""
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


# ---------------------------------------------------------------- text helpers


def clean_text(text: str) -> str:
    """NFC, non-breaking spaces to spaces, whitespace collapsed, trimmed."""
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def text_lines(node: Node) -> list[str]:
    """Visible text of ``node`` split at block boundaries and ``<br>`` (empty lines dropped)."""
    buf: list[str] = []

    def walk(current: Node) -> None:
        for child in current.children:
            if isinstance(child, str):
                buf.append(child)
                continue
            block = child.tag in BLOCK_TAGS
            buf.append("\n" if block else (" " if child.tag in {"td", "th"} else ""))
            walk(child)
            if block:
                buf.append("\n")

    walk(node)
    return [line for line in (clean_text(s) for s in "".join(buf).split("\n")) if line]


def node_text(node: Node) -> str:
    """All visible text of ``node`` on one line."""
    return " ".join(text_lines(node))


def inline_runs(node: Node) -> list[tuple[str, str]]:
    """``(kind, text)`` runs: ``i``/``span``/``b`` elements vs plain ``text`` between them."""
    out: list[tuple[str, str]] = []
    pending: list[str] = []

    def flush() -> None:
        text = clean_text("".join(pending))
        pending.clear()
        if text:
            out.append(("text", text))

    def walk(current: Node) -> None:
        for child in current.children:
            if isinstance(child, str):
                pending.append(child)
            elif child.tag in INLINE_RUN_KINDS:
                flush()
                text = node_text(child)
                if text:
                    out.append((INLINE_RUN_KINDS[child.tag], text))
            elif child.tag in BLOCK_TAGS:
                flush()
                walk(child)
                flush()
            else:
                walk(child)

    walk(node)
    flush()
    return out


# ---------------------------------------------------------------- listing page


def parse_listing(html: str) -> list[tuple[str, str]]:
    """``[(matt, name)]`` of every procedure link (``a.tthc-name``) on a listing page, deduped."""
    seen: set[str] = set()
    items: list[tuple[str, str]] = []
    for node in parse_html(html).iter():
        if node.tag != "a" or not node.has_class("tthc-name"):
            continue
        match = DETAIL_HREF_RE.match(node.attrs.get("href", "").strip())
        name = node_text(node)
        if match and name and match.group(1) not in seen:
            seen.add(match.group(1))
            items.append((match.group(1), name))
    return items


def listing_total(html: str) -> int | None:
    """The ``totalRecord`` count printed under a listing (``None`` when absent)."""
    node = parse_html(html).find(lambda n: n.attrs.get("id") == "totalRecord")
    text = node_text(node) if node else ""
    return int(text) if text.isdigit() else None


# ---------------------------------------------------------------- detail page


def _table_rows(detail: Node) -> list[list[str]]:
    """Rows of every table in a section; headings become one-cell case-label rows."""
    rows: list[list[str]] = []
    has_table = False

    def walk(node: Node) -> None:
        nonlocal has_table
        for child in node.children:
            if not isinstance(child, Node):
                continue
            if child.tag == "table":
                has_table = True
                rows.extend(_rows_of(child))
            elif child.tag in HEADING_TAGS or (child.tag == "p" and node_text(child).endswith(":")):
                heading = node_text(child)
                if heading:
                    rows.append([heading])
            else:
                walk(child)

    walk(detail)
    return rows if has_table else []


def _rows_of(table: Node) -> list[list[str]]:
    out: list[list[str]] = []
    for tr in (n for n in table.iter() if n.tag == "tr"):
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag in {"td", "th"}]
        if not cells or all(c.tag == "th" for c in cells):
            continue
        texts = [node_text(c) for c in cells]
        if any(texts) and texts[0].casefold() != "tên giấy tờ":
            out.append(texts)
    return out


def _form_links(detail: Node) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for li in (n for n in detail.iter() if n.tag == "li"):
        anchor = li.find(lambda n: n.tag == "a" and bool(n.attrs.get("href", "").strip()))
        if anchor is None:
            continue
        span = li.find(lambda n: n.tag == "span")
        name = node_text(span) if span else node_text(li).replace("Tải về", "").strip()
        url = anchor.attrs["href"].strip()
        if name and all(link["url"] != url for link in links):
            links.append({"ten": name, "url": url})
    return links


def parse_detail(html: str) -> dict[str, Any]:
    """Parse one procedure page into ``{ten, sections, tables, form_links, runs}``.

    ``sections`` maps each accordion label to its text (one line per block), ``tables`` maps a
    label to its table rows (heading rows have one cell), ``runs`` keeps the inline structure
    used to split deadlines and fees per channel.
    """
    root = parse_html(html)
    title = root.find(lambda n: n.has_class("tthc-title"))
    heading = title.find(lambda n: n.tag == "h4") if title else None
    parsed: dict[str, Any] = {
        "ten": node_text(heading) if heading else "",
        "sections": {},
        "tables": {},
        "form_links": [],
        "runs": {},
    }
    for item in (n for n in root.iter() if n.has_class("tthc-list-item")):
        label_node = item.find(lambda n: n.attrs.get("aria-controls", "").startswith("collapse"))
        detail = item.find(lambda n: n.has_class("tthc-list-item-detail"))
        label = node_text(label_node) if label_node else ""
        if not label or detail is None or label in parsed["sections"]:
            continue
        parsed["sections"][label] = "\n".join(text_lines(detail))
        parsed["runs"][label] = inline_runs(detail)
        rows = _table_rows(detail)
        if rows:
            parsed["tables"][label] = rows
        if label.casefold() == "biểu mẫu":
            parsed["form_links"] = _form_links(detail)
    return parsed


# ---------------------------------------------------------------- field helpers


def fee_amounts(text: str) -> list[int]:
    """Amounts in VND written with a currency word (``20.000 đồng``, ``50.000đ``), in order."""
    out: list[int] = []
    for match in FEE_RE.finditer(text or ""):
        value = int(match.group(1).replace(".", ""))
        if value not in out:
            out.append(value)
    return out


def channel_code(text: str) -> str:
    """``truc_tiep`` / ``truc_tuyen`` / ``buu_chinh`` / ``khac`` from a channel label."""
    folded = clean_text(text).casefold()
    if "trực tiếp" in folded:
        return "truc_tiep"
    if "trực tuyến" in folded:
        return "truc_tuyen"
    if "bưu chính" in folded:
        return "buu_chinh"
    return "khac"


def level_from_agency(agency: str | None) -> str | None:
    """``xa`` / ``tinh`` / ``bo`` from the implementing agency text (``None`` when unclear)."""
    folded = clean_text(agency or "").casefold()
    if re.search(r"\bxã\b(?!\s+hội)", folded):
        return "xa"
    if re.search(r"\btỉnh\b", folded):
        return "tinh"
    if re.search(r"\b(?:bộ|cục)\b", folded):
        return "bo"
    return None


def _section(parsed: dict[str, Any], *labels: str) -> str:
    wanted = {label.casefold() for label in labels}
    for label, text in parsed["sections"].items():
        if label.casefold() in wanted:
            return str(text)
    return ""


def _runs(parsed: dict[str, Any], label: str) -> list[tuple[str, str]]:
    for key, runs in parsed["runs"].items():
        if key.casefold() == label.casefold():
            return [tuple(r) for r in runs]  # type: ignore[misc]
    return []


def _one_line(text: str) -> str | None:
    return clean_text(text) or None


def _strip_bullet(text: str) -> str:
    return re.sub(r"^[\s*+\-–•]+", "", text).strip()


def _case_label(text: str) -> str | None:
    return _strip_bullet(text).rstrip(" :").strip() or None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------- channels, deadlines, fees


def _channel_key(text: str, known: frozenset[str]) -> str | None:
    key = clean_text(text).casefold().rstrip(" :")
    return key if key in known else None


def _segment(
    runs: list[tuple[str, str]], known: frozenset[str]
) -> dict[str, list[tuple[str, str]]]:
    """Split runs at channel-name markers; empty dict when the section is not per channel."""
    segments: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for kind, text in runs:
        key = _channel_key(text, known) if kind in {"text", "b"} else None
        if key is not None:
            current = key
            segments.setdefault(key, [])
        elif current is not None:
            segments[current].append((kind, text))
    return segments


def _only_channels_or_deadlines(line: str, known: frozenset[str]) -> bool:
    rest = clean_text(line).casefold()
    for name in sorted(known, key=len, reverse=True):
        rest = rest.replace(name, " ")
    rest = DEADLINE_RE.sub(" ", rest)
    return not re.sub(r"[\s.,;:\-]+", "", rest)


@dataclass(slots=True)
class _Fee:
    text: str | None
    amounts: list[int]
    unclear: bool = False


def is_unclear_fee(text: str) -> bool:
    """True for fee text that states nothing usable (a bare number, a stray agency name)."""
    folded = clean_text(text).casefold()
    if not folded:
        return False
    if re.fullmatch(r"[\d.,\s]+", folded):
        return True
    return not re.search(r"\d", folded) and not any(w in folded for w in FEE_WORDS)


def is_none_fee(text: str | None) -> bool:
    """True for 'Không', 'Không thu lệ phí', 'Miễn phí' and similar."""
    return (
        bool(text)
        and NONE_FEE_RE.fullmatch(clean_text(text or "").casefold().rstrip(" .;")) is not None
    )


def _fee_text(text: str, amounts: list[int]) -> _Fee:
    text = text.strip().rstrip(";, ").strip()
    if is_unclear_fee(text):
        return _Fee(None, [], unclear=True)
    return _Fee(text or None, amounts + [a for a in fee_amounts(text) if a not in amounts])


def _fee_from_segment(runs: list[tuple[str, str]], known: frozenset[str]) -> _Fee:
    text = clean_text(" ".join(t for _, t in runs))
    if _only_channels_or_deadlines(text, known):
        return _Fee(None, [])
    match = STRUCTURED_FEE_RE.match(text)
    if match is None:
        return _fee_text(text, [])
    bare, rest = match.group("amt"), match.group("rest")
    amounts = [int(bare.replace(".", ""))] if bare else []
    if _only_channels_or_deadlines(rest, known):
        rest = ""
    if not rest.strip():
        return _Fee(bare, amounts)
    return _fee_text(rest, amounts)


def _fee_from_lines(section: str, known: frozenset[str]) -> _Fee:
    kept: list[str] = []
    for line in section.split("\n"):
        line = clean_text(line)
        if line and not _only_channels_or_deadlines(line, known) and line not in kept:
            kept.append(line)
    return _fee_text(" ".join(kept), [])


def _fee_parts(parsed: dict[str, Any], known: frozenset[str]) -> list[Callable[[str], _Fee]]:
    parts: list[Callable[[str], _Fee]] = []
    for label in ("Phí", "Lệ Phí"):
        segments = _segment(_runs(parsed, label), known)
        if segments:
            parts.append(lambda key, s=segments: _fee_from_segment(s.get(key, []), known))
        else:
            fee = _fee_from_lines(_section(parsed, label), known)
            parts.append(lambda key, f=fee: f)
    return parts


def _combine_fees(fees: list[_Fee]) -> _Fee:
    """Merge the 'Phí' and 'Lệ Phí' parts of one channel (an unclear part blanks the fee)."""
    if any(f.unclear for f in fees):
        return _Fee(None, [], unclear=True)
    informative = [f for f in fees if f.text and not is_none_fee(f.text)]
    if not informative:
        return _Fee(next((f.text for f in fees if f.text), None), [])
    if len(informative) == 1 or informative[0].text == informative[1].text:
        return _Fee(informative[0].text, informative[0].amounts)
    amounts: list[int] = []
    for fee in informative:
        amounts += [a for a in fee.amounts if a not in amounts]
    phi, le_phi = fees
    return _Fee(f"Phí: {phi.text}; Lệ phí: {le_phi.text}", amounts)


def _deadline(runs: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """``(thoi_han, mo_ta)`` of one channel segment of the deadline section."""
    limit = next((t for k, t in runs if k == "i"), None)
    notes: list[str] = []
    for kind, text in runs:
        if kind == "i":
            continue
        if limit is None and (match := DEADLINE_RE.match(text)):
            limit, text = match.group(0), text[match.end() :]
        text = re.sub(r"^[\s*+\-–•:.;,]+", "", text).strip()
        if text:
            notes.append(text)
    return limit, _one_line(" ".join(notes))


def _channel_names(parsed: dict[str, Any]) -> tuple[list[str], list[str]]:
    """``(channel labels, free-text lines)`` of the 'Cách thức thực hiện' section."""
    lines = [ln for ln in _section(parsed, "Cách thức thực hiện").split("\n") if ln]
    names: list[str] = []
    for line in lines:
        label = clean_text(line).rstrip(" :")
        if len(label) <= 60 and channel_code(label) != "khac" and label not in names:
            names.append(label)
    return names, ([] if names else lines)


def _channel_entry(key_text: str, deadline: tuple[str | None, str | None], fee: _Fee) -> dict:
    return {
        "kenh": channel_code(key_text),
        "kenh_text": _clip(key_text, CHANNEL_TEXT_MAX),
        "thoi_han": deadline[0],
        "phi_le_phi": fee.text,
        "phi_vnd": fee.amounts,
        "mo_ta": deadline[1],
    }


def build_channels(parsed: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    """``cach_thuc`` entries: one per channel with its deadline and fee (C2)."""
    names, free = _channel_names(parsed)
    known = KNOWN_CHANNELS | {n.casefold() for n in names}
    deadline_segments = _segment(_runs(parsed, "Thời hạn giải quyết"), known)
    labels = {n.casefold(): n for n in names}
    for key in deadline_segments:
        labels.setdefault(key, key[:1].upper() + key[1:])
    fee_parts = _fee_parts(parsed, known)
    whole_deadline = _one_line(_section(parsed, "Thời hạn giải quyết"))
    if free:
        free_text = _strip_bullet(free[0]) or free[0]
        fee = _combine_fees([part("") for part in fee_parts])
        _warn_fee(fee, warnings)
        entry = _channel_entry(free_text, (whole_deadline, _one_line(" ".join(free))), fee)
        return [entry | {"kenh": "khac"}]
    out: list[dict[str, Any]] = []
    for key, text in labels.items():
        if deadline_segments:
            deadline = _deadline(deadline_segments.get(key, []))
        else:
            deadline = (whole_deadline, None)
        fee = _combine_fees([part(key) for part in fee_parts])
        _warn_fee(fee, warnings)
        out.append(_channel_entry(text, deadline, fee))
    return out


def _warn_fee(fee: _Fee, warnings: list[str]) -> None:
    def add(code: str, message: str) -> None:
        if not any(w.startswith(code + ":") for w in warnings):
            warnings.append(f"{code}: {message}")

    if fee.unclear:
        add(
            "phi_khong_ro", "mục phí không nêu được mức phí (chỉ có số trần hoặc chữ lạ) — để trống"
        )
    if any(amount > FEE_ALERT_VND for amount in fee.amounts):
        add("phi_bat_thuong", f"có mức phí > {FEE_ALERT_VND:,} đồng — cần người kiểm tra nguồn")


# ---------------------------------------------------------------- documents, laws, forms, steps


def _form_code(form_cell: str, name: str) -> str | None:
    match = FORM_CODE_RE.search(form_cell) or FORM_CODE_IN_NAME_RE.search(name)
    return match.group(1) if match else None


def _count(cell: str, key: str) -> int | None:
    match = COUNT_RE[key].search(cell)
    return int(match.group(1)) if match else None


def build_documents(rows: list[list[str]], warnings: list[str]) -> list[dict[str, Any]]:
    """``thanh_phan_ho_so`` from table rows; one-cell rows set the case label ('Lưu ý' skipped)."""
    docs: list[dict[str, Any]] = []
    case: str | None = None
    for row in rows:
        if len(row) == 1:
            case = _case_label(row[0])
            continue
        name = _strip_bullet(row[0])
        if not name or (case or "").casefold().startswith("lưu ý"):
            continue
        if len(docs) >= MAX_DOCS:
            warnings.append(f"thanh_phan_ho_so: quá {MAX_DOCS} giấy tờ, bỏ phần sau")
            break
        if len(name) > DOC_NAME_MAX:
            warnings.append(f"ten_giay_to_cat: d{len(docs) + 1:02d} dài {len(name)} ký tự")
        form_cell = row[1] if len(row) >= 3 else ""
        docs.append(
            {
                "doc_key": f"d{len(docs) + 1:02d}",
                "truong_hop": case,
                "ten_giay_to": _clip(name, DOC_NAME_MAX),
                "ban_chinh": _count(row[-1], "ban_chinh"),
                "ban_sao": _count(row[-1], "ban_sao"),
                "mau": _form_code(form_cell, name),
            }
        )
    return docs


def _law_number(text: str) -> str | None:
    match = LAW_NUMBER_RE.search(text)
    return match.group(0).rstrip("-") if match else None


def build_legal_refs(parsed: dict[str, Any]) -> list[dict[str, str | None]]:
    """``can_cu_phap_ly``: ``{so_hieu, ten}`` per law line (or per table row)."""
    refs: list[dict[str, str | None]] = []
    rows = [r for r in parsed["tables"].get("Căn cứ pháp lý", []) if len(r) >= 2]
    if rows:
        pairs = [(_law_number(r[0]) or _law_number(" ".join(r)), r[1] or r[0]) for r in rows]
    else:
        pairs = []
        for line in _section(parsed, "Căn cứ pháp lý").split("\n"):
            title, _, number = clean_text(line).partition(" Số:")
            pairs.append((_law_number(number) or _law_number(title), title.strip()))
    for number, title in pairs:
        ref = {"so_hieu": number, "ten": clean_text(title)}
        if ref["ten"] and ref not in refs:
            refs.append(ref)
    return refs


def build_forms(parsed: dict[str, Any], source_url: str) -> list[dict[str, str]]:
    """``bieu_mau``: form name + absolute https URL on the same site."""
    forms: list[dict[str, str]] = []
    for link in parsed["form_links"]:
        url = urljoin(source_url, link["url"])
        if urlsplit(url).scheme == "https" and not re.search(r"\s", url):
            forms.append({"ten": clean_text(link["ten"]), "url": url})
    return forms


def build_steps(section: str) -> list[str]:
    """``trinh_tu``: one entry per line; a leading ``-`` bullet is dropped (``+`` kept)."""
    steps = [re.sub(r"^[-–•]\s*", "", clean_text(line)) for line in section.split("\n")]
    return [s for s in steps if s]


# ---------------------------------------------------------------- record


def procedure_code(parsed: dict[str, Any]) -> str | None:
    """``Mã thủ tục`` when it is a valid procedure id, else ``None``."""
    code = clean_text(_section(parsed, "Mã thủ tục"))
    return code if PROCEDURE_ID_RE.match(code) else None


def sections_raw(parsed: dict[str, Any]) -> dict[str, str]:
    """Every section label → NFC text with whitespace collapsed, capped at 8 000 chars."""
    return {
        clean_text(label)[:LABEL_MAX]: clean_text(text)[:SECTION_MAX]
        for label, text in parsed["sections"].items()
        if clean_text(label)
    }


def to_record(
    parsed: dict[str, Any], meta: dict[str, Any], *, warnings: list[str] | None = None
) -> dict[str, Any]:
    """Build a TTHC record v1 (C2) from ``parse_detail`` output and crawl ``meta``.

    ``meta`` carries ``source_url, source_portal, agency, matt, linh_vuc_code, fetched_at,
    sha256_raw, license_note`` (and optionally ``name`` from the listing). ``updated_at`` and
    ``effective_date`` stay ``null``: the portal does not publish them.
    """
    warnings = warnings if warnings is not None else []
    code = procedure_code(parsed)
    agency = _one_line(_section(parsed, "Cơ quan thực hiện"))
    record: dict[str, Any] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "procedure_id": code or f"bca-{meta['matt']}",
        "ma_thu_tuc": code,
        "ten": _clip(clean_text(parsed.get("ten") or meta.get("name") or ""), TITLE_MAX),
        "linh_vuc": _one_line(_section(parsed, "Lĩnh vực")),
        "co_quan_thuc_hien": agency,
        "cap_thuc_hien": level_from_agency(agency),
        "muc_do_dvc": _one_line(_section(parsed, "Mức độ cung cấp dịch vụ công trực tuyến")),
        "doi_tuong": _one_line(_section(parsed, "Đối tượng thực hiện")),
        "cach_thuc": build_channels(parsed, warnings),
        "trinh_tu": build_steps(_section(parsed, "Trình tự thực hiện")),
        "thanh_phan_ho_so": build_documents(parsed["tables"].get("Thành phần hồ sơ", []), warnings),
        "yeu_cau_dieu_kien": _one_line(_section(parsed, "Yêu cầu - điều kiện")),
        "can_cu_phap_ly": build_legal_refs(parsed),
        "bieu_mau": build_forms(parsed, meta["source_url"]),
        "ket_qua": "; ".join(_section(parsed, "Kết quả thực hiện").split("\n")) or None,
        "sections_raw": sections_raw(parsed),
    }
    record["meta"] = _record_meta(meta, content_sha256_of(record))
    return record


def _record_meta(meta: dict[str, Any], sha256_content: str) -> dict[str, Any]:
    return {
        "source_url": meta["source_url"],
        "source_portal": meta["source_portal"],
        "agency": meta["agency"],
        "matt": str(meta["matt"]),
        "linh_vuc_code": meta.get("linh_vuc_code"),
        "fetched_at": meta["fetched_at"],
        "sha256_raw": meta["sha256_raw"],
        "sha256_content": sha256_content,
        "updated_at": None,
        "effective_date": None,
        "license_note": meta["license_note"],
        "parser_version": PARSER_VERSION,
    }

"""Parser for dichvucong.bocongan.gov.vn procedure pages (ADR-007 C2) on trimmed real fixtures."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import jsonschema
import pytest

from ctcv_agent.rag.types import ProcedureRecord, content_sha256_of
from ctcv_core.config import load_config
from ctcv_data import tthc_bca

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tthc"
BASE = "https://dichvucong.bocongan.gov.vn"
LICENSE = 'Ghi rõ nguồn "Cổng Dịch vụ công - Bộ Công an" khi sử dụng lại'


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _meta(matt: str, code: str = "QL_CU_TRU") -> dict:
    return {
        "source_url": f"{BASE}/bocongan/bothutuc/tthc?matt={matt}",
        "source_portal": "Cổng Dịch vụ công - Bộ Công an",
        "agency": "Bộ Công an",
        "matt": matt,
        "linh_vuc_code": code,
        "fetched_at": "2026-09-25T01:02:03.456Z",
        "sha256_raw": "a" * 64,
        "license_note": LICENSE,
    }


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    path = repo_root / "config" / "schemas" / "tthc-record.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _record(matt: str, code: str = "QL_CU_TRU", warnings: list | None = None) -> dict:
    parsed = tthc_bca.parse_detail(_html(f"tthc_{matt}.html"))
    return tthc_bca.to_record(parsed, _meta(matt, code), warnings=warnings)


# ---------------------------------------------------------------- listing


def test_parse_listing_returns_unique_matt_and_names() -> None:
    items = tthc_bca.parse_listing(_html("list_QL_CU_TRU.html"))
    assert len(items) == 11 == len({m for m, _ in items})
    assert items[0] == ("26345", "Gia hạn tạm trú")
    assert ("26360", "Đăng ký thường trú") in items
    assert all(m.isdigit() and n for m, n in items)
    assert tthc_bca.listing_total(_html("list_QL_CU_TRU.html")) == 11


def test_parse_listing_ignores_other_links() -> None:
    html = (
        '<a href="/bocongan/bothutuc/tthc?matt=1" class="tthc-name">A</a>'
        '<a href="/bocongan/bothutuc/tthc?matt=1" class="tthc-name">A lặp</a>'
        '<a href="https://evil.example/tthc?matt=2" class="tthc-name">B</a>'
        '<a href="/bocongan/bothutuc/tthc?matt=3">không có lớp tthc-name</a>'
    )
    assert tthc_bca.parse_listing(html) == [("1", "A")]
    assert tthc_bca.listing_total(html) is None


# ---------------------------------------------------------------- detail


def test_parse_detail_sections_tables_forms() -> None:
    parsed = tthc_bca.parse_detail(_html("tthc_26360.html"))
    assert parsed["ten"] == "Đăng ký thường trú"
    assert len(parsed["sections"]) == 14
    assert parsed["sections"]["Mã thủ tục"] == "1.004222"
    assert parsed["sections"]["Cơ quan thực hiện"] == "Công an Xã"
    rows = parsed["tables"]["Thành phần hồ sơ"]
    assert rows[0] == [
        "* Trường hợp công dân đăng ký thường trú vào chỗ ở hợp pháp thuộc quyền sở hữu của mình:"
    ]
    assert all(r and r[0] != "Tên giấy tờ" for r in rows)
    assert parsed["form_links"] == [
        {
            "ten": "Tờ khai thay đổi thông tin cư trú (Mẫu CT01 ban hành kèm theo Thông tư số "
            "56/2021/TT-BCA)",
            "url": "/public_dir/tttl/01/giayto/2023_10/1698204115_CT01.doc",
        }
    ]


def test_detail_sections_stop_at_their_own_div() -> None:
    parsed = tthc_bca.parse_detail(_html("tthc_26356.html"))
    assert parsed["sections"]["Kết quả thực hiện"].endswith(
        "Phiếu từ chối tiếp nhận, giải quyết hồ sơ"
    )
    assert "CỔNG DỊCH VỤ CÔNG" not in json.dumps(parsed, ensure_ascii=False)


# ---------------------------------------------------------------- record 26360 (fee per channel)


def test_record_26360_is_schema_valid_and_matches_model(schema: dict) -> None:
    record = _record("26360")
    jsonschema.validate(record, schema)
    model = ProcedureRecord.model_validate(record)
    assert model.content_sha256() == record["meta"]["sha256_content"]
    assert record["meta"]["sha256_content"] == content_sha256_of(record)
    assert record["procedure_id"] == record["ma_thu_tuc"] == "1.004222"
    assert record["cap_thuc_hien"] == "xa"
    assert record["meta"]["updated_at"] is None and record["meta"]["effective_date"] is None
    assert record["meta"]["parser_version"] == "tthc-bca/1"


def test_record_26360_channels_deadlines_and_fees() -> None:
    direct, online = _record("26360")["cach_thuc"]
    assert (direct["kenh"], direct["kenh_text"]) == ("truc_tiep", "Trực tiếp")
    assert (online["kenh"], online["kenh_text"]) == ("truc_tuyen", "Trực tuyến")
    assert direct["thoi_han"] == online["thoi_han"] == "07 Ngày làm việc"
    assert direct["phi_vnd"] == [20000] and online["phi_vnd"] == [10000]
    assert direct["phi_le_phi"] == (
        "Trường hợp công dân nộp hồ sơ trực tiếp thu 20.000 đồng/lần đăng ký"
    )
    assert online["phi_le_phi"].endswith("thu 10.000 đồng/lần đăng ký.")
    assert direct["mo_ta"].startswith("Nộp hồ sơ trực tiếp tại Công an cấp xã. Thời gian tiếp nhận")


def test_record_26360_documents() -> None:
    docs = _record("26360")["thanh_phan_ho_so"]
    assert [d["doc_key"] for d in docs] == [f"d{i:02d}" for i in range(1, len(docs) + 1)]
    first_case = (
        "Trường hợp công dân đăng ký thường trú vào chỗ ở hợp pháp thuộc quyền sở hữu của mình"
    )
    d01, d02, d03 = docs[:3]
    assert d01["truong_hop"] == first_case and d01["ten_giay_to"].startswith("Giấy tờ, tài liệu")
    assert (d01["ban_chinh"], d01["ban_sao"], d01["mau"]) == (0, 1, None)
    assert (d02["ban_chinh"], d02["ban_sao"], d02["mau"]) == (1, 0, "CT02")
    assert d03["mau"] == "CT01" and d03["ten_giay_to"].startswith("Tờ khai thay đổi")
    assert docs[3]["truong_hop"].startswith("Đăng ký thường trú tại chỗ ở hợp pháp không thuộc")
    assert not any((d["truong_hop"] or "").startswith("Lưu ý") for d in docs)


def test_record_26360_steps_laws_forms_result() -> None:
    record = _record("26360")
    assert (
        record["trinh_tu"][0]
        == "Bước 1: Cá nhân, tổ chức chuẩn bị hồ sơ theo quy định của pháp luật."
    )
    assert any(s.startswith("+ Trường hợp hồ sơ đã đầy đủ") for s in record["trinh_tu"])
    laws = record["can_cu_phap_ly"]
    assert laws[0] == {"so_hieu": "68/2020/QH14", "ten": "Luật 68/2020/QH14"}
    assert {"so_hieu": "75/2022/TT-BTC"}.items() <= laws[-1].items()
    assert record["bieu_mau"] == [
        {
            "ten": "Tờ khai thay đổi thông tin cư trú (Mẫu CT01 ban hành kèm theo Thông tư số "
            "56/2021/TT-BCA)",
            "url": BASE + "/public_dir/tttl/01/giayto/2023_10/1698204115_CT01.doc",
        }
    ]
    assert record["ket_qua"].startswith(
        "Cập nhật thông tin trong Cơ sở dữ liệu quốc gia về dân cư; "
    )
    assert record["yeu_cau_dieu_kien"] == "không"


def test_sections_raw_is_nfc_collapsed_and_capped() -> None:
    raw = _record("26360")["sections_raw"]
    assert len(raw) == 14
    for label, text in raw.items():
        assert unicodedata.is_normalized("NFC", text) and unicodedata.is_normalized("NFC", label)
        assert "  " not in text and "\n" not in text and len(text) <= 8000
    parsed = tthc_bca.parse_detail(_html("tthc_26360.html"))
    parsed["sections"]["Trình tự thực hiện"] = "x " * 6000
    capped = tthc_bca.to_record(parsed, _meta("26360"))["sections_raw"]["Trình tự thực hiện"]
    assert len(capped) == 8000


# ---------------------------------------------------------------- 26356 (ul/li layout, bad fee)


def test_record_26356_ul_layout_and_uninterpretable_fee(schema: dict) -> None:
    warnings: list[str] = []
    record = _record("26356", warnings=warnings)
    jsonschema.validate(record, schema)
    assert record["procedure_id"] == "1.004194"
    channels = record["cach_thuc"]
    assert [c["kenh"] for c in channels] == ["truc_tiep", "truc_tuyen"]
    assert all(c["thoi_han"] == "03 Ngày làm việc" for c in channels)
    assert channels[1]["mo_ta"].startswith("Nộp hồ sơ trực tuyến qua các cổng")
    # The portal shows a bare "1" as the fee: never turned into a number or into "free".
    assert all(c["phi_le_phi"] is None and c["phi_vnd"] == [] for c in channels)
    assert any("phi_khong_ro" in w for w in warnings)
    d01 = record["thanh_phan_ho_so"][0]
    assert d01["truong_hop"] == "Hồ sơ đăng ký tạm trú gồm"
    assert d01["ten_giay_to"].startswith("Tờ khai thay đổi thông tin cư trú (Mẫu CT01")
    assert (d01["mau"], d01["ban_chinh"], d01["ban_sao"]) == ("CT01", 1, 0)


# ---------------------------------------------------------------- record 26052 (single deadline)


def test_record_26052_single_deadline_free_and_laws(schema: dict) -> None:
    record = _record("26052", "CAP_CCCD")
    jsonschema.validate(record, schema)
    assert record["procedure_id"] == "2.000200"
    assert record["cap_thuc_hien"] is None  # "trật tự xã hội" is not the commune level
    channels = record["cach_thuc"]
    assert [c["kenh"] for c in channels] == ["truc_tiep", "truc_tuyen"]
    assert all(c["thoi_han"] == "07 ngày làm việc" for c in channels)
    assert all(c["phi_le_phi"] == "Không" and c["phi_vnd"] == [] for c in channels)
    laws = {law["so_hieu"]: law["ten"] for law in record["can_cu_phap_ly"]}
    assert laws["26/2023/QH15"] == "Luật Căn cước"
    assert "190/2025/NQ-QH15" in laws
    assert record["thanh_phan_ho_so"][0]["mau"] == "DC02"


# ---------------------------------------------------------------- helpers


@pytest.mark.parametrize(
    ("text", "amounts"),
    [
        ("thu 20.000 đồng/lần đăng ký", [20000]),
        ("Lệ phí : 50.000đ/giấy thông hành", [50000]),
        ("1.500.000 VNĐ; 200.000 đồng", [1500000, 200000]),
        ("12000 Đồng", [12000]),
        ("3 đơn vị, 02 bản chà số máy", []),
        ("Không", []),
    ],
)
def test_fee_amounts(text: str, amounts: list[int]) -> None:
    assert tthc_bca.fee_amounts(text) == amounts


@pytest.mark.parametrize(
    ("text", "kenh"),
    [
        ("Trực tiếp", "truc_tiep"),
        ("Trực tuyến", "truc_tuyen"),
        ("Dịch vụ bưu chính", "buu_chinh"),
        ("Bưu chính", "buu_chinh"),
        ("Qua ứng dụng", "khac"),
    ],
)
def test_channel_code(text: str, kenh: str) -> None:
    assert tthc_bca.channel_code(text) == kenh


@pytest.mark.parametrize(
    ("agency", "level"),
    [
        ("Công an Xã", "xa"),
        ("Công an xã, phường, thị trấn .", "xa"),
        ("Công an tỉnh", "tinh"),
        ("Cục quản lý xuất nhập cảnh", "bo"),
        ("Bộ Công an", "bo"),
        ("Phòng cảnh sát quản lý hành chính về trật tự xã hội", None),
        (None, None),
    ],
)
def test_level_from_agency(agency: str | None, level: str | None) -> None:
    assert tthc_bca.level_from_agency(agency) == level


def test_missing_code_falls_back_to_bca_matt(schema: dict) -> None:
    parsed = tthc_bca.parse_detail(_html("tthc_26356.html"))
    parsed["sections"]["Mã thủ tục"] = "không có mã"
    record = tthc_bca.to_record(parsed, _meta("26356"))
    assert record["ma_thu_tuc"] is None and record["procedure_id"] == "bca-26356"
    jsonschema.validate(record, schema)


def test_segmented_deadline_in_list_items() -> None:
    html = (
        '<div class="tthc-title"><h4>Thủ tục thử</h4></div>'
        '<div class="tthc-list-item"><div aria-controls="collapse1a">Cách thức thực hiện<i></i>'
        "</div>"
        '<div class="tthc-list-item-detail"><ul><li><b>Trực tiếp</b></li><li><b>Dịch vụ bưu chính'
        "</b></li></ul></div></div>"
        '<div class="tthc-list-item"><div aria-controls="collapse5a">Thời hạn giải quyết<i></i>'
        '</div><div class="tthc-list-item-detail"><ul><li> Trực tiếp </li><li><i>5 Ngày làm việc'
        "</i> <span>tại trụ sở.<br> Không quá 05 ngày</span> Dịch vụ bưu chính </li><li><i>8 Ngày"
        "</i> <span>qua bưu điện</span></li></ul></div></div>"
        '<div class="tthc-list-item"><div aria-controls="collapse11a">Lệ Phí<i></i></div>'
        '<div class="tthc-list-item-detail"><ul><li> 200.000đ</li></ul></div></div>'
    )
    record = tthc_bca.to_record(tthc_bca.parse_detail(html), _meta("7"))
    post = record["cach_thuc"][1]
    assert (post["kenh"], post["thoi_han"], post["mo_ta"]) == (
        "buu_chinh",
        "8 Ngày",
        "qua bưu điện",
    )
    assert record["cach_thuc"][0]["mo_ta"] == "tại trụ sở. Không quá 05 ngày"
    assert all(
        c["phi_le_phi"] == "200.000đ" and c["phi_vnd"] == [200000] for c in record["cach_thuc"]
    )
    assert record["ma_thu_tuc"] is None and record["procedure_id"] == "bca-7"


def test_fixtures_are_small_and_free_of_contact_data_and_tokens() -> None:
    patterns = [re.compile(p["regex"]) for p in load_config("guardrails")["pii_patterns"]]
    for path in sorted(FIXTURES.glob("*.html")):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert len(raw) <= 15_000, path.name
        assert text.startswith("<!-- Nguồn: Cổng Dịch vụ công - Bộ Công an"), path.name
        assert not any(p.search(text) for p in patterns), path.name
        lowered = text.lower()
        for needle in ("csrf", "token", "sso", "password", "<script", "@", "email"):
            assert needle not in lowered, (path.name, needle)


@pytest.mark.parametrize(
    ("text", "unclear"),
    [("1", True), ("a", True), ("Công an Xã", True), ("Không", False), ("Chưa quy định.", False)]
    + [("10 USD/lần", False), ("thu 20.000 đồng", False), ("", False)],
)
def test_unclear_fee_text(text: str, unclear: bool) -> None:
    assert tthc_bca.is_unclear_fee(text) is unclear


@pytest.mark.parametrize(
    ("text", "none"),
    [("Không", True), ("Không thu lệ phí", True), ("Miễn phí.", True), ("không có", True)]
    + [("Chưa quy định.", False), ("200.000đ", False), (None, False)],
)
def test_none_fee_text(text: str | None, none: bool) -> None:
    assert tthc_bca.is_none_fee(text) is none


def test_stray_agency_name_in_fee_is_blanked_and_huge_fee_is_flagged() -> None:
    parsed = tthc_bca.parse_detail(_html("tthc_26052.html"))
    parsed["sections"]["Phí"] = "Công an Xã"
    parsed["runs"]["Phí"] = [("text", "Công an Xã")]
    warnings: list[str] = []
    channels = tthc_bca.to_record(parsed, _meta("26052"), warnings=warnings)["cach_thuc"]
    assert all(c["phi_le_phi"] is None for c in channels)
    assert [w.split(":")[0] for w in warnings] == ["phi_khong_ro"]
    parsed["sections"]["Phí"] = "25.000.000đ/giấy thông hành"
    parsed["runs"]["Phí"] = [("text", "25.000.000đ/giấy thông hành")]
    warnings.clear()
    channels = tthc_bca.to_record(parsed, _meta("26052"), warnings=warnings)["cach_thuc"]
    assert channels[0]["phi_vnd"] == [25_000_000]
    assert [w.split(":")[0] for w in warnings] == ["phi_bat_thuong"]

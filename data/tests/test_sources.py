"""sources.yaml: allow-list, crawl rules and rejection of stray domains."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ctcv_core.errors import ValidationFailed
from ctcv_data.sources import host_of, is_same_or_subdomain, load_sources

REQUIRED_DOMAINS = {
    "dichvucong.gov.vn",
    "vneid.gov.vn",
    "bocongan.gov.vn",
    "gdt.gov.vn",
    "thuedientu.gdt.gov.vn",
    "ais.gov.vn",
    "chongluadao.vn",
    "khonggianmang.vn",
}


def test_real_sources_file_is_valid(repo_root: Path) -> None:
    cfg = load_sources(repo_root / "data" / "sources.yaml")
    assert REQUIRED_DOMAINS <= set(cfg.domains())
    assert cfg.rules.rate_limit_rps <= 1
    assert cfg.rules.respect_robots and cfg.rules.only_guide_pages
    banks = [d for d in cfg.allowlist if d.source_type == "ngan_hang"]
    assert 2 <= len(banks) <= 3
    assert all(d.status == "can_xac_nhan" for d in banks)
    assert all(cfg.is_allowlisted(s.url) for s in cfg.sources)
    assert all(s.url.startswith("https://") for s in cfg.sources)


def test_every_allowlisted_domain_has_purpose_and_agency(repo_root: Path) -> None:
    cfg = load_sources(repo_root / "data" / "sources.yaml")
    for domain in cfg.allowlist:
        assert domain.purpose and domain.agency, domain.domain


def test_subdomain_matching() -> None:
    assert is_same_or_subdomain("thuedientu.gdt.gov.vn", "gdt.gov.vn")
    assert not is_same_or_subdomain("gdt.gov.vn.evil.com", "gdt.gov.vn")
    assert not is_same_or_subdomain("fakegdt.gov.vn", "gdt.gov.vn")
    assert host_of("https://WWW.Example.VN/path?q=1") == "www.example.vn"


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _minimal() -> dict:
    return {
        "version": 1,
        "crawl_rules": {"rate_limit_rps": 1, "respect_robots": True},
        "allowlist": [
            {
                "domain": "dichvucong.gov.vn",
                "agency": "DVC",
                "source_type": "co_quan_nha_nuoc",
                "purpose": "hướng dẫn",
                "status": "da_xac_nhan",
            }
        ],
        "sources": [
            {
                "url": "https://dichvucong.gov.vn/x",
                "agency": "DVC",
                "source_type": "co_quan_nha_nuoc",
                "license_note": "n",
            }
        ],
    }


def test_stray_domain_is_rejected(tmp_path: Path) -> None:
    data = _minimal()
    data["sources"].append(
        {
            "url": "https://evil.example/x",
            "agency": "?",
            "source_type": "ngan_hang",
            "license_note": "",
        }
    )
    with pytest.raises(ValidationFailed, match="không nằm trong allowlist") as excinfo:
        load_sources(_write(tmp_path, data))
    assert excinfo.value.details["problems"]


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: d["crawl_rules"].update(rate_limit_rps=5), "rate_limit_rps"),
        (lambda d: d["crawl_rules"].update(respect_robots=False), "respect_robots"),
        (lambda d: d["allowlist"][0].update(status="ok"), "status"),
        (lambda d: d["allowlist"][0].update(source_type="blog"), "source_type"),
        (lambda d: d["sources"][0].update(url="http://dichvucong.gov.vn/x"), "https"),
    ],
)
def test_rule_violations(tmp_path: Path, mutate, needle: str) -> None:
    data = _minimal()
    mutate(data)
    with pytest.raises(ValidationFailed, match=needle):
        load_sources(_write(tmp_path, data))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed, match="Thiếu"):
        load_sources(tmp_path / "none.yaml")


TTHC_CODES = {
    "QL_CU_TRU",
    "CAP_CCCD",
    "G01-CA27",
    "G01-CA28",
    "PT_GIAO_THONG",
    "QL_XUAT_NHAP_CANH",
    "G01-CA13",
    "NP_GIAO_THONG",
    "G01-CA26",
}


def test_real_sources_have_min_interval_and_tthc_seeds(repo_root: Path) -> None:
    cfg = load_sources(repo_root / "data" / "sources.yaml")
    assert cfg.rules.min_interval_s >= 1.2
    assert cfg.rules.min_interval_s >= 1 / cfg.rules.rate_limit_rps
    assert "bothutuc" in cfg.rules.guide_path_hints
    tthc = [s for s in cfg.sources if "/bocongan/bothutuc" in s.url]
    codes = {s.url.split("linh_vuc=")[1].split("&")[0] for s in tthc}
    assert codes == TTHC_CODES and len(tthc) == len(TTHC_CODES)
    for seed in tthc:
        assert seed.url.startswith("https://dichvucong.bocongan.gov.vn/bocongan/bothutuc?")
        assert seed.url.endswith("&per_page=50")
        assert seed.agency == "Cổng Dịch vụ công - Bộ Công an"
        assert seed.source_type == "co_quan_nha_nuoc"
        assert seed.tos_checked_on is None and seed.robots_ok is True
        assert 'Ghi rõ nguồn "Cổng Dịch vụ công - Bộ Công an"' in seed.license_note
        assert cfg.domain_for(seed.url).domain == "bocongan.gov.vn"


def test_min_interval_defaults_to_one_over_rate(tmp_path: Path) -> None:
    data = _minimal()
    data["crawl_rules"]["rate_limit_rps"] = 0.5
    assert load_sources(_write(tmp_path, data)).rules.min_interval_s == 2.0


def test_min_interval_shorter_than_rate_is_rejected(tmp_path: Path) -> None:
    data = _minimal()
    data["crawl_rules"]["min_interval_s"] = 0.5
    with pytest.raises(ValidationFailed, match="min_interval_s"):
        load_sources(_write(tmp_path, data))


def test_domain_for_picks_most_specific_and_rejects_strays(tmp_path: Path) -> None:
    data = _minimal()
    data["allowlist"].append(
        {
            "domain": "bocongan.gov.vn",
            "agency": "BCA",
            "source_type": "co_quan_nha_nuoc",
            "purpose": "p",
            "status": "da_xac_nhan",
        }
    )
    cfg = load_sources(_write(tmp_path, data))
    assert cfg.domain_for("https://dichvucong.bocongan.gov.vn/x").agency == "BCA"
    assert cfg.domain_for("https://dichvucong.gov.vn/x").agency == "DVC"
    assert cfg.domain_for("https://evil.example/x") is None

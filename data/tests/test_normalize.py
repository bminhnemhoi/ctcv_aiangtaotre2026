"""Step 2 — normalize: raw TTHC pages → schema-valid records + normalize_report.json (C1/C2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from ctcv_data.pipeline import PipelineConfig
from ctcv_data.pipeline import normalize as normalize_step
from ctcv_data.pipeline.__main__ import main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tthc"
HOST = "https://dichvucong.bocongan.gov.vn"
UA = "CTCV-crawler/0.1 (test)"


def _row(kind: str, url: str, when: str, body: bytes, status: int = 200, **info) -> dict:
    return {
        "url": url,
        "kind": kind,
        "matt": info.get("matt"),
        "linh_vuc_code": info.get("code"),
        "name": info.get("name"),
        "fetched_at": when,
        "http_status": status,
        "bytes": len(body),
        "sha256_raw": hashlib.sha256(body).hexdigest(),
        "path": info.get("path"),
        "robots_allowed": True,
        "user_agent": UA,
    }


def _detail(raw: Path, matt: str, body: bytes, when: str, code: str, name: str | None) -> dict:
    target = raw / "tthc" / "bca" / f"tthc_{matt}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    url = f"{HOST}/bocongan/bothutuc/tthc?matt={matt}"
    return _row("detail", url, when, body, matt=matt, code=code, name=name, path=str(target))


@pytest.fixture
def crawled(tmp_path: Path) -> PipelineConfig:
    """Raw dir as ``crawl --online`` leaves it (request stamps 1.5 s apart).

    1 listing, 4 good pages (one duplicates 26360), 1 empty page, 1 HTTP 404.
    """
    raw = tmp_path / "raw"
    fx = {m: (FIXTURES / f"tthc_{m}.html").read_bytes() for m in ("26360", "26356", "26052")}
    stamps = [f"2026-09-25T01:00:{s:06.3f}Z" for s in (0, 1.5, 3, 4.5, 6, 7.5, 9)]
    listing = (FIXTURES / "list_QL_CU_TRU.html").read_bytes()
    rows = [
        _row("listing", f"{HOST}/bocongan/bothutuc?linh_vuc=QL_CU_TRU", stamps[0], listing),
        _detail(raw, "26360", fx["26360"], stamps[1], "QL_CU_TRU", "Đăng ký thường trú"),
        _detail(raw, "26356", fx["26356"], stamps[2], "QL_CU_TRU", "Đăng ký tạm trú"),
        _detail(raw, "26052", fx["26052"], stamps[3], "CAP_CCCD", None),
        _detail(raw, "99999", fx["26360"], stamps[4], "QL_CU_TRU", "Đăng ký thường trú"),
        _detail(raw, "88888", b"<html><body></body></html>", stamps[5], "QL_CU_TRU", None),
        _row("detail", f"{HOST}/bocongan/bothutuc/tthc?matt=77777", stamps[6], b"", 404),
    ]
    manifest = raw / "tthc" / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return PipelineConfig(root=tmp_path, raw_dir=raw, clean_dir=tmp_path / "clean")


def _config_root(cfg: PipelineConfig, repo_root: Path) -> PipelineConfig:
    cfg.root = repo_root  # real config/ + data/sources.yaml; raw/clean stay in tmp
    return cfg


def test_skipped_without_raw_tthc(tmp_path: Path, repo_root: Path) -> None:
    cfg = PipelineConfig(root=repo_root, raw_dir=tmp_path / "raw", clean_dir=tmp_path / "c")
    report = normalize_step.run(cfg)
    assert report.status == "skipped" and report.exit_code == 0
    assert report.message == "chưa có dữ liệu thô TTHC — chạy crawl --online trước"
    assert not (tmp_path / "c").exists()


def test_records_are_written_and_schema_valid(crawled: PipelineConfig, repo_root: Path) -> None:
    cfg = _config_root(crawled, repo_root)
    report = normalize_step.run(cfg)
    assert report.status == "ok", report.message
    records = cfg.clean() / "tthc" / "records"
    assert sorted(p.name for p in records.glob("*.json")) == [
        "1.004194.json",
        "1.004222.json",
        "2.000200.json",
    ]
    schema = json.loads((repo_root / "config/schemas/tthc-record.schema.json").read_text("utf-8"))
    for path in records.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "\\u" not in text  # ensure_ascii=False
        record = json.loads(text)
        jsonschema.validate(record, schema)
    first = json.loads((records / "1.004222.json").read_text(encoding="utf-8"))
    meta = first["meta"]
    assert meta["matt"] == "26360" and meta["fetched_at"] == "2026-09-25T01:00:01.500Z"
    assert meta["agency"] == "Bộ Công an"
    assert meta["source_portal"] == "Cổng Dịch vụ công - Bộ Công an"
    assert meta["license_note"].startswith('Ghi rõ nguồn "Cổng Dịch vụ công - Bộ Công an"')
    raw = (FIXTURES / "tthc_26360.html").read_bytes()
    assert meta["sha256_raw"] == hashlib.sha256(raw).hexdigest()


def test_report_counts_coverage_and_interval(crawled: PipelineConfig, repo_root: Path) -> None:
    cfg = _config_root(crawled, repo_root)
    normalize_step.run(cfg)
    path = cfg.clean() / "tthc" / "normalize_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["parser_version"] == "tthc-bca/1"
    assert report["generated_at"].endswith("Z")
    assert (report["pages_detail"], report["records_valid"], report["records_invalid"]) == (5, 3, 1)
    assert report["invalid"][0]["matt"] == "88888" and report["invalid"][0]["errors"]
    assert any("1.004222" in w and "99999" in w for w in report["warnings"])
    assert any(w.startswith("26356: phi_khong_ro") for w in report["warnings"])
    assert report["coverage"] == {
        "cach_thuc": 100.0,
        "phi_vnd": 33.3,
        "thanh_phan_ho_so": 100.0,
        "trinh_tu": 100.0,
        "can_cu_phap_ly": 100.0,
        "bieu_mau": 100.0,
    }
    assert report["by_linh_vuc"] == {"Đăng ký, quản lý cư trú": 2, "Cấp, quản lý căn cước": 1}
    assert report["by_linh_vuc_code"] == {"QL_CU_TRU": 2, "CAP_CCCD": 1}
    assert report["min_request_interval_s"] == 1.5
    assert report["procedure_ids"] == ["1.004194", "1.004222", "2.000200"]


def test_rerun_is_idempotent_and_drops_stale_records(
    crawled: PipelineConfig, repo_root: Path
) -> None:
    cfg = _config_root(crawled, repo_root)
    normalize_step.run(cfg)
    records = cfg.clean() / "tthc" / "records"
    before = {p.name: p.read_bytes() for p in records.glob("*.json")}
    (records / "old-procedure.json").write_text("{}", encoding="utf-8")
    normalize_step.run(cfg)
    after = {p.name: p.read_bytes() for p in records.glob("*.json")}
    assert after == before


def test_tampered_raw_file_is_invalid(crawled: PipelineConfig, repo_root: Path) -> None:
    cfg = _config_root(crawled, repo_root)
    page = cfg.raw() / "tthc" / "bca" / "tthc_26052.html"
    page.write_bytes(page.read_bytes() + b"<!-- changed -->")
    normalize_step.run(cfg)
    report = json.loads((cfg.clean() / "tthc" / "normalize_report.json").read_text("utf-8"))
    bad = {i["matt"]: i["errors"] for i in report["invalid"]}
    assert "sha256" in bad["26052"][0]
    assert not (cfg.clean() / "tthc" / "records" / "2.000200.json").exists()


def test_cli_normalize_with_dirs(
    crawled: PipelineConfig, repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["normalize", "--root", str(repo_root)]
    argv += ["--raw-dir", str(crawled.raw()), "--clean-dir", str(crawled.clean())]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "[OK] normalize" in out and "3 bản ghi hợp lệ" in out


def test_min_interval_helper() -> None:
    stamps = ["2026-09-25T01:00:03.000Z", "2026-09-25T01:00:00.000Z", "2026-09-25T01:00:01.25Z"]
    assert normalize_step.min_request_interval(stamps) == 1.25
    assert normalize_step.min_request_interval(stamps[:1]) is None


def test_review_html_lists_flagged_pages(crawled: PipelineConfig, repo_root: Path) -> None:
    cfg = _config_root(crawled, repo_root)
    report = normalize_step.run(cfg)
    review = cfg.clean() / "tthc" / "review_flagged.html"
    assert str(review) in report.outputs
    text = review.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>") and "phi_khong_ro" in text
    assert "tthc?matt=26356" in text and "tthc?matt=88888" in text
    assert text.count('<section class="flag">') <= normalize_step.REVIEW_LIMIT
    assert "<script" not in text


def test_content_change_since_last_run_is_reported(
    crawled: PipelineConfig, repo_root: Path
) -> None:
    cfg = _config_root(crawled, repo_root)
    normalize_step.run(cfg)
    report_path = cfg.clean() / "tthc" / "normalize_report.json"
    assert json.loads(report_path.read_text("utf-8"))["content_changed"] == []
    record_path = cfg.clean() / "tthc" / "records" / "1.004194.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["meta"]["sha256_content"] = "0" * 64
    record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    normalize_step.run(cfg)
    assert json.loads(report_path.read_text("utf-8"))["content_changed"] == ["1.004194"]

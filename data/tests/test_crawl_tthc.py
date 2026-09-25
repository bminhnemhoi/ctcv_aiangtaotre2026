"""Online TTHC crawl (ADR-007 C1): robots, allow-list, one shared pace, manifest, raw files.

Every test injects a fake fetcher and a fake clock — no network is touched.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from ctcv_data.manifest import read_manifest
from ctcv_data.pipeline import PipelineConfig
from ctcv_data.pipeline import crawl as crawl_step
from ctcv_data.sources import load_sources

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tthc"
HOST = "https://dichvucong.bocongan.gov.vn"
LIST_CU_TRU = f"{HOST}/bocongan/bothutuc?linh_vuc=QL_CU_TRU&per_page=50"
LIST_CCCD = f"{HOST}/bocongan/bothutuc?linh_vuc=CAP_CCCD&per_page=50"
ROBOTS_OK = b"User-agent: Googlebot\nDisallow: /tttl/\n"
MANIFEST_KEYS = {
    "url",
    "kind",
    "matt",
    "linh_vuc_code",
    "name",
    "fetched_at",
    "http_status",
    "bytes",
    "sha256_raw",
    "path",
    "robots_allowed",
    "user_agent",
}


class FakeClock:
    """Monotonic clock + sleep + UTC wall clock that only move when told to."""

    def __init__(self) -> None:
        self.t = 0.0
        self.base = dt.datetime(2026, 9, 25, 1, 0, 0, tzinfo=dt.UTC)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += max(0.0, seconds)

    def now(self) -> dt.datetime:
        return self.base + dt.timedelta(seconds=self.t)


class FakeSite:
    """``url -> (status, body)``; records the clock time of every request."""

    def __init__(self, clock: FakeClock, pages: dict[str, tuple[int, bytes] | Exception]) -> None:
        self.clock = clock
        self.pages = pages
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append((url, self.clock.t))
        self.clock.t += 0.3  # response time
        page = self.pages.get(url, (404, b"not found"))
        if isinstance(page, Exception):
            raise page
        return page


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _detail(matt: str) -> str:
    return f"{HOST}/bocongan/bothutuc/tthc?matt={matt}"


def _site_pages(robots: tuple[int, bytes] | Exception = (200, ROBOTS_OK)) -> dict:
    return {
        f"{HOST}/robots.txt": robots,
        LIST_CU_TRU: (200, _fixture("list_QL_CU_TRU.html")),
        _detail("26360"): (200, _fixture("tthc_26360.html")),
        _detail("26356"): (200, _fixture("tthc_26356.html")),
    }


def _sources(repo_root: Path, **rules):
    cfg = load_sources(repo_root / "data" / "sources.yaml")
    return replace(cfg, rules=replace(cfg.rules, **rules)) if rules else cfg


def _run(tmp_path: Path, repo_root: Path, site_pages: dict, seeds=(LIST_CU_TRU,), **rules):
    clock = FakeClock()
    site = FakeSite(clock, site_pages)
    cfg = PipelineConfig(root=tmp_path, raw_dir=tmp_path / "raw", online=True)
    summary = crawl_step.crawl_tthc(
        cfg,
        _sources(repo_root, **rules),
        list(seeds),
        fetcher=site,
        pacer=crawl_step.Pacer(1.2, clock=clock.monotonic, sleep=clock.sleep),
        now=clock.now,
    )
    return summary, site, cfg


def _manifest(cfg: PipelineConfig) -> list[dict]:
    path = crawl_step.tthc_manifest_path(cfg)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_crawl_fetches_robots_listing_then_details(tmp_path: Path, repo_root: Path) -> None:
    summary, site, cfg = _run(tmp_path, repo_root, _site_pages())
    urls = [u for u, _ in site.calls]
    assert urls[0] == f"{HOST}/robots.txt" and urls[1] == LIST_CU_TRU
    assert len(urls) == len(set(urls)) == 2 + 11
    assert all(u.startswith(HOST + "/") for u in urls)
    assert summary["detail_ok"] == 2 and summary["detail_failed"] == 9
    assert summary["links_found"] == 11 and summary["listed_total"] == 11
    assert summary["off_allowlist_requests"] == 0
    assert summary["hosts_contacted"] == ["dichvucong.bocongan.gov.vn"]


def test_one_shared_pace_between_any_two_requests(tmp_path: Path, repo_root: Path) -> None:
    _, site, cfg = _run(tmp_path, repo_root, _site_pages())
    starts = [t for _, t in site.calls]
    gaps = [b - a for a, b in zip(starts, starts[1:], strict=False)]
    assert min(gaps) >= 1.2
    stamps = [dt.datetime.fromisoformat(r["fetched_at"]) for r in _manifest(cfg)]
    wall_gaps = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:], strict=False)]
    assert min(wall_gaps) >= 1.2


def test_manifest_lines_and_raw_files(tmp_path: Path, repo_root: Path) -> None:
    _, _, cfg = _run(tmp_path, repo_root, _site_pages())
    rows = _manifest(cfg)
    assert [r["kind"] for r in rows] == ["listing"] + ["detail"] * 11
    for row in rows:
        assert set(row) == MANIFEST_KEYS
        assert row["fetched_at"].endswith("Z") and len(row["sha256_raw"]) == 64
        assert row["robots_allowed"] is True and row["user_agent"].startswith("CTCV-crawler")
    listing, first = rows[0], rows[1]
    assert (listing["linh_vuc_code"], listing["matt"], listing["name"]) == ("QL_CU_TRU", None, None)
    assert listing["path"] == "raw/tthc/bca/list_QL_CU_TRU.html"
    ok = {r["matt"]: r for r in rows if r["http_status"] == 200 and r["kind"] == "detail"}
    assert set(ok) == {"26360", "26356"}
    body = _fixture("tthc_26360.html")
    assert ok["26360"]["sha256_raw"] == hashlib.sha256(body).hexdigest()
    assert ok["26360"]["bytes"] == len(body) and ok["26360"]["name"] == "Đăng ký thường trú"
    assert (tmp_path / ok["26360"]["path"]).read_bytes() == body
    assert first["matt"] == "26345" and first["http_status"] == 404 and first["path"] is None


@pytest.mark.parametrize(
    "robots",
    [(503, b"busy"), TimeoutError("timed out"), (200, b"User-agent: *\nDisallow: /bocongan/\n")],
)
def test_robots_error_or_disallow_blocks_the_domain(
    tmp_path: Path, repo_root: Path, robots
) -> None:
    summary, site, cfg = _run(tmp_path, repo_root, _site_pages(robots))
    assert [u for u, _ in site.calls] == [f"{HOST}/robots.txt"]
    assert summary["robots_disallowed"] == 1 and summary["detail_ok"] == 0
    assert _manifest(cfg) == []


def test_robots_404_means_allowed(tmp_path: Path, repo_root: Path) -> None:
    summary, _, _ = _run(tmp_path, repo_root, _site_pages((404, b"")))
    assert summary["detail_ok"] == 2


def test_max_pages_per_domain_caps_detail_requests(tmp_path: Path, repo_root: Path) -> None:
    summary, site, _ = _run(tmp_path, repo_root, _site_pages(), max_pages_per_domain=2)
    assert len(site.calls) == 2 + 2 and summary["capped"] is True


def test_detail_listed_twice_is_fetched_once(tmp_path: Path, repo_root: Path) -> None:
    pages = _site_pages() | {LIST_CCCD: (200, _fixture("list_QL_CU_TRU.html"))}
    summary, site, cfg = _run(tmp_path, repo_root, pages, seeds=(LIST_CU_TRU, LIST_CCCD))
    urls = [u for u, _ in site.calls]
    assert len(urls) == len(set(urls)) == 3 + 11
    details = [r for r in _manifest(cfg) if r["kind"] == "detail"]
    assert {r["linh_vuc_code"] for r in details} == {"QL_CU_TRU"}


def test_network_error_is_recorded_not_fatal(tmp_path: Path, repo_root: Path) -> None:
    pages = _site_pages() | {_detail("26360"): OSError("connection reset")}
    summary, _, cfg = _run(tmp_path, repo_root, pages)
    row = next(r for r in _manifest(cfg) if r["matt"] == "26360")
    assert row["http_status"] == 0 and row["path"] is None and len(row["sha256_raw"]) == 64
    assert summary["detail_ok"] == 1


def test_seed_off_allowlist_is_never_requested(tmp_path: Path, repo_root: Path) -> None:
    summary, site, _ = _run(
        tmp_path, repo_root, _site_pages(), seeds=("https://evil.example/bocongan/bothutuc?x=1",)
    )
    assert site.calls == [] and summary["off_allowlist_blocked"] == 1


def test_hash_change_since_last_crawl_is_warned(tmp_path: Path, repo_root: Path) -> None:
    _run(tmp_path, repo_root, _site_pages())
    pages = _site_pages() | {_detail("26360"): (200, _fixture("tthc_26360.html") + b"\n")}
    summary, _, _ = _run(tmp_path, repo_root, pages)
    assert summary["hash_changed"] == [_detail("26360")]


def test_redirect_off_allowlist_is_refused(repo_root: Path) -> None:
    handler = crawl_step.AllowlistRedirectHandler(load_sources(repo_root / "data" / "sources.yaml"))
    with pytest.raises(crawl_step.OffAllowlistError):
        handler.check_redirect("https://evil.example/x")
    with pytest.raises(crawl_step.OffAllowlistError):
        handler.check_redirect(HOST.replace("https", "http") + "/x")
    handler.check_redirect(HOST + "/bocongan/bothutuc/tthc?matt=1")


def test_pacer_waits_only_the_remaining_time() -> None:
    clock = FakeClock()
    pacer = crawl_step.Pacer(1.2, clock=clock.monotonic, sleep=clock.sleep)
    pacer.wait()
    assert clock.t == 0.0
    pacer.done()
    clock.t += 0.5
    pacer.wait()
    assert clock.t == pytest.approx(1.2)


def test_offline_run_keeps_tthc_seeds_out_of_guides_manifest(
    tmp_path: Path, repo_root: Path
) -> None:
    cfg = PipelineConfig(root=repo_root, raw_dir=tmp_path / "raw")
    report = crawl_step.run(cfg)
    assert report.status == "ok" and report.details["tthc_seeds"] == 9
    entries = read_manifest(tmp_path / "raw" / "guides" / "manifest.jsonl")
    assert entries and not any("/bocongan/bothutuc" in e.url for e in entries)
    assert not (tmp_path / "raw" / "tthc").exists()


def test_tthc_seed_detection(repo_root: Path) -> None:
    data = yaml.safe_load((repo_root / "data" / "sources.yaml").read_text(encoding="utf-8"))
    seeds = [s["url"] for s in data["sources"] if crawl_step.is_tthc_seed(s["url"])]
    assert len(seeds) == 9
    assert not crawl_step.is_tthc_seed("https://bocongan.gov.vn/")

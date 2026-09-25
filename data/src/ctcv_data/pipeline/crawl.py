"""Step 1 — crawl (E01: offline dry run; ADR-007: online crawl of public procedure pages).

The dry run parses ``data/sources.yaml``, verifies every seed URL is allow-listed and writes
a manifest skeleton (``status: pending``) to ``data/raw/guides/manifest.jsonl``. With
``--online`` it additionally fetches ``robots.txt`` for each domain of the ordinary seeds and
marks disallowed seeds as ``skipped``.

Seeds whose URL contains ``/bocongan/bothutuc`` (field listings of the Ministry of Public
Security portal, ADR-007) are crawled for real when ``--online`` is given: robots.txt is read
once per host (5xx or timeout = whole host forbidden, RFC 9309), the listing is fetched, then
every procedure page it links to. One :class:`Pacer` spaces *any* two requests by at least
``crawl_rules.min_interval_s``; only allow-listed https hosts are ever contacted (redirects
included). Raw HTML goes to ``data/raw/tthc/bca/`` and one manifest line per request to
``data/raw/tthc/manifest.jsonl`` (ADR-007 C1).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from ctcv_core.errors import ValidationFailed
from ctcv_data import tthc_bca
from ctcv_data.manifest import MANIFEST_NAME, ManifestEntry, write_manifest
from ctcv_data.pipeline import PipelineConfig, StepReport
from ctcv_data.sources import CrawlRules, SourcesConfig, host_of, load_sources

GUIDES_DIRNAME = "guides"
TTHC_DIRNAME = "tthc"
BCA_DIRNAME = "bca"
TTHC_SEED_MARK = "/bocongan/bothutuc"
DETAIL_PATH = "/bocongan/bothutuc/tthc?matt="
Fetcher = Callable[[str], tuple[int, bytes]]


def manifest_path(cfg: PipelineConfig) -> Path:
    """``data/raw/guides/manifest.jsonl`` under the configured raw dir."""
    return cfg.raw() / GUIDES_DIRNAME / MANIFEST_NAME


def build_entries(sources: SourcesConfig) -> list[ManifestEntry]:
    """Manifest skeleton: one pending entry per seed URL (only allow-listed URLs get here)."""
    return [
        ManifestEntry(
            url=s.url,
            agency=s.agency,
            source_type=s.source_type,
            license_note=s.license_note,
            notes=s.notes,
        )
        for s in sources.sources
    ]


def fetch_robots(
    domain: str, rules: CrawlRules, sources: SourcesConfig | None = None
) -> dict[str, Any]:
    """Fetch ``https://<domain>/robots.txt`` once and return a small status dict.

    With ``sources`` a redirect is only followed to an allow-listed https URL.
    """
    url = f"https://{domain}/robots.txt"
    request = urllib.request.Request(url, headers={"User-Agent": rules.user_agent})
    checked_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    handlers = [AllowlistRedirectHandler(sources)] if sources is not None else []
    try:
        with urllib.request.build_opener(*handlers).open(request, timeout=rules.timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, OffAllowlistError) as exc:
        return {"fetched": False, "error": str(exc), "checked_at": checked_at}
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    return {"fetched": True, "parser": parser, "checked_at": checked_at}


def annotate_robots(
    entries: list[ManifestEntry], sources: SourcesConfig, pacer: Pacer | None = None
) -> int:
    """Online mode: one robots.txt request per domain, paced by ``pacer`` or ``rate_limit_rps``."""
    rules = sources.rules
    per_domain: dict[str, dict[str, Any]] = {}
    disallowed = 0
    for entry in entries:
        domain = host_of(entry.url)
        if domain not in per_domain:
            if pacer is not None:
                pacer.wait()
            elif per_domain:
                time.sleep(1.0 / rules.rate_limit_rps)
            per_domain[domain] = fetch_robots(domain, rules, sources)
            if pacer is not None:
                pacer.done()
        info = per_domain[domain]
        parser = info.get("parser")
        allowed = None if parser is None else parser.can_fetch(rules.user_agent, entry.url)
        entry.robots = {
            "fetched": info["fetched"],
            "allowed": allowed,
            "checked_at": info["checked_at"],
            **({"error": info["error"]} if "error" in info else {}),
        }
        if allowed is False:
            entry.status = "skipped"
            entry.notes = (entry.notes + " robots.txt không cho phép.").strip()
            disallowed += 1
    return disallowed


# ---------------------------------------------------------------- shared pace, allow-list guard


@dataclass(slots=True)
class Pacer:
    """One rate limiter for the whole run.

    ``min_interval_s`` separates the end of a request from the start of the next one, so the
    start-to-start gap between any two requests is never shorter either.
    """

    min_interval_s: float
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    last_done: float | None = None

    def wait(self) -> None:
        """Sleep until ``min_interval_s`` has passed since the previous request finished."""
        if self.last_done is None:
            return
        remaining = self.min_interval_s - (self.clock() - self.last_done)
        if remaining > 0:
            self.sleep(remaining)

    def done(self) -> None:
        """Mark the end of a request."""
        self.last_done = self.clock()


class OffAllowlistError(RuntimeError):
    """A URL (or redirect target) outside the https allow-list — it is never requested."""


class AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when the target is an allow-listed https URL."""

    def __init__(self, sources: SourcesConfig) -> None:
        """Keep the allow-list used to vet redirect targets."""
        super().__init__()
        self.sources = sources

    def check_redirect(self, url: str) -> None:
        """Raise :class:`OffAllowlistError` unless ``url`` is https and allow-listed."""
        if urlsplit(url).scheme != "https" or not self.sources.is_allowlisted(url):
            raise OffAllowlistError(url)

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        """Vet ``newurl`` before letting urllib follow the redirect."""
        self.check_redirect(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def urllib_fetcher(sources: SourcesConfig) -> Fetcher:
    """Real fetcher: project User-Agent and timeout from ``sources.yaml``; 4xx/5xx returned."""
    rules = sources.rules
    opener = urllib.request.build_opener(AllowlistRedirectHandler(sources))

    def fetch(url: str) -> tuple[int, bytes]:
        request = urllib.request.Request(url, headers={"User-Agent": rules.user_agent})
        try:
            with opener.open(request, timeout=rules.timeout_s) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read() if exc.fp is not None else b""

    return fetch


# ---------------------------------------------------------------- TTHC crawl (ADR-007)


def is_tthc_seed(url: str) -> bool:
    """True for a procedure-listing seed of the Ministry of Public Security portal."""
    return TTHC_SEED_MARK in url


def tthc_manifest_path(cfg: PipelineConfig) -> Path:
    """``data/raw/tthc/manifest.jsonl`` under the configured raw dir."""
    return cfg.raw() / TTHC_DIRNAME / MANIFEST_NAME


def _utc_stamp(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _field_code(url: str) -> str | None:
    code = (parse_qs(urlsplit(url).query).get("linh_vuc") or [""])[0]
    return re.sub(r"[^A-Za-z0-9_-]", "_", code) or None


def _is_https_allowlisted(sources: SourcesConfig, url: str) -> bool:
    return urlsplit(url).scheme == "https" and sources.is_allowlisted(url)


@dataclass(slots=True)
class _Robots:
    """Robots verdict for one host: a parser, allow-all (4xx) or deny-all (5xx/timeout)."""

    parser: urllib.robotparser.RobotFileParser | None
    allow_all: bool

    def allows(self, user_agent: str, url: str) -> bool:
        if self.parser is not None:
            return self.parser.can_fetch(user_agent, url)
        return self.allow_all


@dataclass
class TthcCrawler:
    """Crawl listing seeds and the procedure pages they link to (one instance per run)."""

    cfg: PipelineConfig
    sources: SourcesConfig
    fetcher: Fetcher
    pacer: Pacer
    now: Callable[[], dt.datetime]
    rows: list[dict[str, Any]] = field(default_factory=list)
    robots: dict[str, _Robots] = field(default_factory=dict)
    hosts: set[str] = field(default_factory=set)
    stats: dict[str, Any] = field(default_factory=dict)

    def request(self, url: str) -> tuple[int, bytes, str]:
        """One paced request to an allow-listed https URL: ``(status, body, fetched_at)``.

        A network error or timeout is returned as status ``0`` with an empty body.
        """
        if not _is_https_allowlisted(self.sources, url):
            raise OffAllowlistError(url)
        self.pacer.wait()
        fetched_at = _utc_stamp(self.now())
        self.hosts.add(host_of(url))
        try:
            status, body = self.fetcher(url)
        except OffAllowlistError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            status, body = 0, b""
        finally:
            self.pacer.done()
        return status, body, fetched_at

    def _robots_for(self, url: str) -> _Robots:
        host = host_of(url)
        if host not in self.robots:
            status, body, _ = self.request(f"https://{host}/robots.txt")
            if status == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
                self.robots[host] = _Robots(parser, True)
            else:  # 4xx: no rules, allowed; 5xx or network error: the whole host is forbidden
                self.robots[host] = _Robots(None, 400 <= status < 500)
        return self.robots[host]

    def allowed(self, url: str) -> bool:
        """Allow-listed https URL that robots.txt lets our User-Agent fetch."""
        if not _is_https_allowlisted(self.sources, url):
            self.stats["off_allowlist_blocked"] += 1
            return False
        if not self._robots_for(url).allows(self.sources.rules.user_agent, url):
            self.stats["robots_disallowed"] += 1
            return False
        return True

    def fetch_page(self, url: str, kind: str, file_name: str, **info: Any) -> bytes | None:
        """Fetch one page, save it when HTTP 200, append its manifest line; body or ``None``."""
        status, body, fetched_at = self.request(url)
        target = self.cfg.raw() / TTHC_DIRNAME / BCA_DIRNAME / file_name
        saved = status == 200 and bool(body)
        if saved:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        self.rows.append(
            {
                "url": url,
                "kind": kind,
                "matt": info.get("matt"),
                "linh_vuc_code": info.get("linh_vuc_code"),
                "name": info.get("name"),
                "fetched_at": fetched_at,
                "http_status": status,
                "bytes": len(body),
                "sha256_raw": hashlib.sha256(body).hexdigest(),
                "path": self._relative(target) if saved else None,
                "robots_allowed": True,
                "user_agent": self.sources.rules.user_agent,
            }
        )
        return body if saved else None

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.cfg.root.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _crawl_detail(self, url: str, matt: str, code: str | None, name: str) -> None:
        if self.allowed(url):
            info = {"matt": matt, "linh_vuc_code": code, "name": name}
            body = self.fetch_page(url, "detail", f"tthc_{matt}.html", **info)
            self.stats["detail_ok" if body else "detail_failed"] += 1

    def crawl_seed(self, seed_url: str, seen: set[str]) -> None:
        """Fetch one listing, then every not-yet-seen procedure page it links to."""
        if not self.allowed(seed_url):
            return
        code = _field_code(seed_url)
        html = self.fetch_page(seed_url, "listing", f"list_{code}.html", linh_vuc_code=code)
        if html is None:
            self.stats["listing_failed"] += 1
            return
        text = html.decode("utf-8", errors="replace")
        self.stats["listed_total"] += tthc_bca.listing_total(text) or 0
        for matt, name in tthc_bca.parse_listing(text):
            self.stats["links_found"] += 1
            url = urljoin(seed_url, DETAIL_PATH + matt)
            if url in seen:
                continue
            if len(seen) >= self.sources.rules.max_pages_per_domain:
                self.stats["capped"] = True
                return
            seen.add(url)
            self._crawl_detail(url, matt, code, name)

    def run(self, seeds: list[str]) -> dict[str, Any]:
        """Crawl every seed in order; return the summary written into the step report."""
        started = time.monotonic()
        counters = ("listed_total", "links_found", "detail_ok", "detail_failed", "listing_failed")
        self.stats = dict.fromkeys(counters, 0)
        self.stats |= {"robots_disallowed": 0, "off_allowlist_blocked": 0, "capped": False}
        seen: set[str] = set()
        for seed in seeds:
            self.crawl_seed(seed, seen)
        off_list = [h for h in self.hosts if not self.sources.is_allowlisted(f"https://{h}/")]
        self.stats |= {
            "seeds": len(seeds),
            "requests": len(self.rows) + len(self.robots),
            "hosts_contacted": sorted(self.hosts),
            "off_allowlist_requests": len(off_list),
            "duration_s": round(time.monotonic() - started, 1),
        }
        return self.stats


def _previous_hashes(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["url"]: r["sha256_raw"] for r in rows if r.get("http_status") == 200}


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def crawl_tthc(
    cfg: PipelineConfig,
    sources: SourcesConfig,
    seeds: list[str],
    *,
    fetcher: Fetcher | None = None,
    pacer: Pacer | None = None,
    now: Callable[[], dt.datetime] | None = None,
) -> dict[str, Any]:
    """Online TTHC crawl of ``seeds``: raw HTML + ``manifest.jsonl``; returns a summary.

    ``fetcher`` (``url -> (status, body)``), ``pacer`` and ``now`` are injectable for tests.
    Pages whose hash differs from the previous manifest are listed in ``hash_changed``.
    """
    crawler = TthcCrawler(
        cfg=cfg,
        sources=sources,
        fetcher=fetcher or urllib_fetcher(sources),
        pacer=pacer or Pacer(sources.rules.min_interval_s),
        now=now or (lambda: dt.datetime.now(dt.UTC)),
    )
    path = tthc_manifest_path(cfg)
    before = _previous_hashes(path)
    try:
        summary = crawler.run(seeds)
    finally:
        _write_rows(path, crawler.rows)
    summary["hash_changed"] = [
        r["url"]
        for r in crawler.rows
        if r["http_status"] == 200 and before.get(r["url"], r["sha256_raw"]) != r["sha256_raw"]
    ]
    summary["manifest"] = str(path)
    return summary


# ---------------------------------------------------------------- step entry point


def _tthc_step(
    cfg: PipelineConfig, sources: SourcesConfig, seeds: list[str], pacer: Pacer
) -> tuple[dict[str, Any] | None, StepReport | None]:
    """Run the online TTHC crawl: ``(summary, None)`` or ``(None, failed report)``."""
    try:
        return crawl_tthc(cfg, sources, seeds, pacer=pacer), None
    except OffAllowlistError as exc:
        message = f"Đã chặn một URL ngoài danh sách cho phép: {exc}"
        return None, StepReport("crawl", "failed", message, {"blocked_url": str(exc)})


def run(cfg: PipelineConfig) -> StepReport:
    """Validate sources, write the guides manifest skeleton; online: robots + TTHC crawl."""
    try:
        sources = load_sources(cfg.root / "data" / "sources.yaml")
    except ValidationFailed as exc:
        return StepReport("crawl", "failed", exc.message_vi, exc.details or {})
    entries = [e for e in build_entries(sources) if not is_tthc_seed(e.url)]
    tthc_seeds = [s.url for s in sources.sources if is_tthc_seed(s.url)]
    pacer = Pacer(sources.rules.min_interval_s)
    disallowed = annotate_robots(entries, sources, pacer) if cfg.online else 0
    out = write_manifest(manifest_path(cfg), entries)
    details: dict[str, Any] = {
        "sources": len(entries),
        "domains": len(sources.domains()),
        "online": cfg.online,
        "disallowed": disallowed,
        "rate_limit_rps": sources.rules.rate_limit_rps,
        "min_interval_s": sources.rules.min_interval_s,
        "tthc_seeds": len(tthc_seeds),
    }
    outputs = [str(out)]
    mode = "online" if cfg.online else "offline (dry run)"
    message = (
        f"{mode}: {len(entries)} URL gốc hướng dẫn, {disallowed} bị robots chặn; "
        f"{len(tthc_seeds)} trang danh sách TTHC"
    )
    if not (cfg.online and tthc_seeds):
        return StepReport("crawl", "ok", message + " (chỉ tải khi có --online).", details, outputs)
    tthc, failed = _tthc_step(cfg, sources, tthc_seeds, pacer)
    if failed is not None or tthc is None:
        return failed or StepReport("crawl", "failed", "Không chạy được bước crawl TTHC.")
    details["tthc"] = tthc
    outputs.append(tthc["manifest"])
    message += (
        f" → {tthc['detail_ok']} trang thủ tục tải được, {tthc['detail_failed']} lỗi, "
        f"{len(tthc['hash_changed'])} trang đổi hash."
    )
    return StepReport("crawl", "ok", message, details, outputs)

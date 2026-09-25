"""``data/sources.yaml`` — allow-listed official domains, crawl rules and seed URLs.

The crawler (plan §7 step 1, epic E03) may only fetch URLs whose host is on the
allow-list; ``load_sources`` refuses a file that breaks that rule, so a stray domain is
caught before any request is made.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ctcv_core.errors import ValidationFailed
from ctcv_core.paths import REPO_ROOT

SOURCES_FILE = "sources.yaml"
# Crawl-level classification (the registry `source_type` of the corpus is co_quan_nha_nuoc).
SOURCE_TYPES: tuple[str, ...] = ("qppl", "co_quan_nha_nuoc", "ngan_hang", "to_chuc_xa_hoi")
DOMAIN_STATUSES: tuple[str, ...] = ("da_xac_nhan", "can_xac_nhan")
MAX_RATE_RPS = 1.0


@dataclass(frozen=True, slots=True)
class CrawlRules:
    """Rate limit and scope rules every crawler run must honour."""

    rate_limit_rps: float
    respect_robots: bool
    only_guide_pages: bool
    user_agent: str
    timeout_s: float
    max_pages_per_domain: int
    guide_path_hints: tuple[str, ...]
    min_interval_s: float = 1.0


@dataclass(frozen=True, slots=True)
class AllowedDomain:
    """One allow-listed domain and why it is trusted."""

    domain: str
    agency: str
    source_type: str
    purpose: str
    status: str
    tos_url: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Source:
    """A seed URL the crawler starts from."""

    url: str
    agency: str
    source_type: str
    license_note: str
    tos_checked_on: str | None = None
    robots_ok: bool | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SourcesConfig:
    """Parsed ``sources.yaml``."""

    rules: CrawlRules
    allowlist: tuple[AllowedDomain, ...]
    sources: tuple[Source, ...]

    def is_allowlisted(self, url: str) -> bool:
        """True when the host of ``url`` is an allow-listed domain or a sub-domain of one."""
        host = host_of(url)
        return bool(host) and any(is_same_or_subdomain(host, d.domain) for d in self.allowlist)

    def domains(self) -> tuple[str, ...]:
        """All allow-listed domains."""
        return tuple(d.domain for d in self.allowlist)

    def domain_for(self, url: str) -> AllowedDomain | None:
        """The most specific allow-listed domain covering ``url`` (``None`` when off-list)."""
        host = host_of(url)
        matches = [d for d in self.allowlist if host and is_same_or_subdomain(host, d.domain)]
        return max(matches, key=lambda d: len(d.domain)) if matches else None


def host_of(url: str) -> str:
    """Lower-cased host name of ``url`` (empty when the URL has none)."""
    return (urlsplit(url).hostname or "").lower()


def is_same_or_subdomain(host: str, domain: str) -> bool:
    """True when ``host`` equals ``domain`` or ends with ``.domain``."""
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def default_sources_path(root: Path | None = None) -> Path:
    """``<root>/data/sources.yaml``."""
    return (root or REPO_ROOT) / "data" / SOURCES_FILE


def _min_interval(raw: dict[str, Any], rate: float, problems: list[str]) -> float:
    """``min_interval_s`` (default ``1 / rate``); it may never be shorter than ``1 / rate``."""
    floor = 1.0 / rate if rate > 0 else 1.0 / MAX_RATE_RPS
    value = float(raw.get("min_interval_s", floor))
    if value < floor:
        problems.append(
            f"crawl_rules.min_interval_s={value} phải ≥ 1/rate_limit_rps = {floor:.3f} giây"
        )
    return value


def _rules(raw: dict[str, Any], problems: list[str]) -> CrawlRules:
    rate = float(raw.get("rate_limit_rps", MAX_RATE_RPS))
    if rate > MAX_RATE_RPS or rate <= 0:
        problems.append(f"crawl_rules.rate_limit_rps={rate} phải trong (0, {MAX_RATE_RPS}]")
    min_interval = _min_interval(raw, rate, problems)
    if raw.get("respect_robots") is not True:
        problems.append("crawl_rules.respect_robots phải là true")
    return CrawlRules(
        rate_limit_rps=rate,
        respect_robots=bool(raw.get("respect_robots", False)),
        only_guide_pages=bool(raw.get("only_guide_pages", True)),
        user_agent=str(raw.get("user_agent", "CTCV-crawler")),
        timeout_s=float(raw.get("timeout_s", 20)),
        max_pages_per_domain=int(raw.get("max_pages_per_domain", 500)),
        guide_path_hints=tuple(str(h) for h in raw.get("guide_path_hints", [])),
        min_interval_s=min_interval,
    )


def _allowlist(raw: list[dict[str, Any]], problems: list[str]) -> tuple[AllowedDomain, ...]:
    out: list[AllowedDomain] = []
    for item in raw:
        domain = str(item.get("domain", "")).lower()
        if not domain or "/" in domain:
            problems.append(f"allowlist: domain không hợp lệ {domain!r}")
        if item.get("source_type") not in SOURCE_TYPES:
            problems.append(f"allowlist[{domain}].source_type phải thuộc {SOURCE_TYPES}")
        if item.get("status") not in DOMAIN_STATUSES:
            problems.append(f"allowlist[{domain}].status phải thuộc {DOMAIN_STATUSES}")
        out.append(
            AllowedDomain(
                domain=domain,
                agency=str(item.get("agency", "")),
                source_type=str(item.get("source_type", "")),
                purpose=str(item.get("purpose", "")),
                status=str(item.get("status", "")),
                tos_url=item.get("tos_url"),
                notes=str(item.get("notes", "")),
            )
        )
    return tuple(out)


def _sources(raw: list[dict[str, Any]], problems: list[str]) -> tuple[Source, ...]:
    out: list[Source] = []
    for item in raw:
        url = str(item.get("url", ""))
        if not url.startswith("https://"):
            problems.append(f"sources: url phải dùng https: {url!r}")
        if item.get("source_type") not in SOURCE_TYPES:
            problems.append(f"sources[{url}].source_type phải thuộc {SOURCE_TYPES}")
        checked = item.get("tos_checked_on")
        out.append(
            Source(
                url=url,
                agency=str(item.get("agency", "")),
                source_type=str(item.get("source_type", "")),
                license_note=str(item.get("license_note", "")),
                tos_checked_on=None if checked is None else str(checked),
                robots_ok=item.get("robots_ok"),
                notes=str(item.get("notes", "")),
            )
        )
    return tuple(out)


def load_sources(path: Path | None = None) -> SourcesConfig:
    """Parse and validate ``sources.yaml``; raise ``ValidationFailed`` listing every problem."""
    path = path or default_sources_path()
    if not path.is_file():
        raise ValidationFailed(f"Thiếu file nguồn crawl: {path}", details={"path": str(path)})
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationFailed(f"{path.name} phải là bảng khóa–giá trị ở cấp cao nhất.")
    problems: list[str] = []
    rules = _rules(raw.get("crawl_rules") or {}, problems)
    allowlist = _allowlist(raw.get("allowlist") or [], problems)
    sources = _sources(raw.get("sources") or [], problems)
    cfg = SourcesConfig(rules=rules, allowlist=allowlist, sources=sources)
    if not allowlist:
        problems.append("allowlist rỗng")
    for source in sources:
        if source.url and not cfg.is_allowlisted(source.url):
            problems.append(f"sources: {source.url} không nằm trong allowlist")
    if problems:
        raise ValidationFailed(
            f"{path.name} không hợp lệ: " + "; ".join(problems[:5]),
            details={"problems": problems},
        )
    return cfg

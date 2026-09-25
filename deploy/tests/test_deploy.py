"""Deterministic tests for deploy/ and .github/ (WP I, brief §16).

Run with ``uv run pytest deploy/tests`` (``deploy`` is in pytest's ``norecursedirs`` so
the root run never picks it up; CI calls it explicitly). Nothing here talks to a
model, a registry or a remote host: every script runs with ``--dry-run`` and Docker is
only used for ``docker compose config`` when a daemon is reachable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy"
SCRIPTS = DEPLOY / "scripts"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SERVICES = ("api", "agent", "speech", "vision")
PORTS = {"api": 8000, "agent": 8010, "speech": 8020, "vision": 8030}
BASH = shutil.which("bash")
DOCKER = shutil.which("docker")

# Fake, non-secret values so dry runs never touch the developer's real .env.
DRY_ENV = {
    "CTCV_ENV_FILE": str(DEPLOY / "tests" / "no-such-env-file"),
    "DEPLOY_HOST": "deploy.example.invalid",
    "DEPLOY_USER": "deploy",
    "DEPLOY_DIR": "/opt/ctcv",
    "APP_DOMAIN": "app.example.invalid",
    "STATUS_DOMAIN": "status.example.invalid",
    "REGISTRY": "ghcr.io/example",
    "TELEGRAM_BOT_TOKEN": "000000:dry-run-token",
    "TELEGRAM_CHAT_ID": "1",
    "CF_API_TOKEN": "dry-run-cf-token",
    "CF_ZONE_ID": "zone",
    "CF_RECORD_ID": "record",
    "PRIMARY_IP": "203.0.113.10",
    "BACKUP_IP": "203.0.113.20",
    "POSTGRES_USER": "ctcv",
    "POSTGRES_DB": "ctcv",
    "BACKUP_DIR": str(DEPLOY / "tests" / "tmp-backups"),
}


def _bash(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **DRY_ENV, **(env or {})}
    return subprocess.run(
        [BASH or "bash", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=120,
        check=False,
    )


def _docker_ready() -> bool:
    if not DOCKER:
        return False
    probe = subprocess.run([DOCKER, "info"], capture_output=True, text=True, check=False)
    return probe.returncode == 0


needs_bash = pytest.mark.skipif(BASH is None, reason="bash is not on PATH")
needs_docker = pytest.mark.skipif(not _docker_ready(), reason="docker daemon not reachable")


# --------------------------------------------------------------------------- scripts
SCRIPT_CASES = [
    ("deploy.sh", ["staging", "--tag", "v0.0.0-test", "--skip-check", "--no-build"]),
    ("rollback.sh", ["v0.0.0-prev"]),
    ("failover.sh", ["--to", "backup"]),
    ("backup.sh", []),
    ("restore-drill.sh", []),
    ("restore_drill.sh", []),
    ("smoke.sh", ["http://127.0.0.1:8000"]),
]


@needs_bash
@pytest.mark.parametrize("name", sorted(p.name for p in SCRIPTS.glob("*.sh")))
def test_script_syntax(name: str) -> None:
    result = _bash("-n", str(SCRIPTS / name))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", sorted(p.name for p in SCRIPTS.glob("*.sh")))
def test_script_is_strict_and_documented(name: str) -> None:
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash"), name
    assert "set -euo pipefail" in text, f"{name} must set -euo pipefail"
    if name != "lib.sh":
        assert "--dry-run" in text, f"{name} must document --dry-run"


@needs_bash
@pytest.mark.parametrize(("name", "args"), SCRIPT_CASES)
def test_script_dry_run(name: str, args: list[str]) -> None:
    result = _bash(str(SCRIPTS / name), *args, "--dry-run")
    assert result.returncode == 0, f"{name} --dry-run failed:\n{result.stdout}\n{result.stderr}"
    assert "[dry-run]" in result.stdout, f"{name} printed no dry-run markers"
    assert DRY_ENV["TELEGRAM_BOT_TOKEN"] not in result.stdout + result.stderr
    assert DRY_ENV["CF_API_TOKEN"] not in result.stdout + result.stderr


@needs_bash
def test_deploy_dry_run_covers_plan_steps() -> None:
    result = _bash(str(SCRIPTS / "deploy.sh"), "prod", "--skip-check", "--no-build", "--dry-run")
    out = result.stdout
    assert result.returncode == 0, result.stderr
    for marker in ("compose pull", "up -d", "alembic upgrade head", "smoke", "telegram"):
        assert marker in out, f"deploy.sh dry-run lacks step '{marker}'"


@needs_bash
def test_deploy_rejects_unknown_env() -> None:
    result = _bash(str(SCRIPTS / "deploy.sh"), "sandbox-env", "--dry-run")
    assert result.returncode != 0


@needs_bash
def test_rollback_requires_tag() -> None:
    result = _bash(str(SCRIPTS / "rollback.sh"), "--dry-run")
    assert result.returncode != 0


@needs_bash
def test_backup_rotation_keeps_14() -> None:
    result = _bash(str(SCRIPTS / "backup.sh"), "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "14" in result.stdout


@needs_bash
def test_failover_switches_dns_only() -> None:
    result = _bash(str(SCRIPTS / "failover.sh"), "--to", "backup", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "proxied" in result.stdout and "false" in result.stdout
    assert DRY_ENV["BACKUP_IP"] in result.stdout


# --------------------------------------------------------------------------- compose
COMPOSE_BASE = DEPLOY / "docker-compose.yml"
COMPOSE_DEV = DEPLOY / "docker-compose.dev.yml"
COMPOSE_PROD = DEPLOY / "docker-compose.prod.yml"
COMPOSE_CI = DEPLOY / "docker-compose.ci.yml"


def _compose_config(*files: Path, profiles: tuple[str, ...] = ("cpu",)) -> dict:
    cmd = [DOCKER or "docker", "compose"]
    for file in files:
        cmd += ["-f", str(file)]
    for profile in profiles:
        cmd += ["--profile", profile]
    cmd += ["config", "--format", "json"]
    env = {**os.environ, "COMPOSE_PROJECT_NAME": "ctcv-test"}
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_compose_files_exist() -> None:
    for file in (COMPOSE_BASE, COMPOSE_DEV, COMPOSE_PROD, COMPOSE_CI):
        assert file.is_file(), file


def test_compose_base_text_contract() -> None:
    text = COMPOSE_BASE.read_text(encoding="utf-8")
    assert "vllm/vllm-openai" in text
    assert "qdrant/qdrant:v1." in text
    assert "postgres:16" in text and "redis:7" in text and "minio/minio" in text
    for svc in SERVICES:
        assert f"deploy/docker/{svc}.Dockerfile" in text
    assert "deploy/docker/web.Dockerfile" in text
    assert "louislam/uptime-kuma" in text and "caddy:2" in text
    assert "--enable-lora" in text, "multi-LoRA flag must be present (commented) per D9 v2"


@needs_docker
def test_compose_cpu_profile_has_no_models() -> None:
    cfg = _compose_config(COMPOSE_BASE, profiles=("cpu",))
    names = set(cfg["services"])
    assert {"postgres", "redis", "qdrant", "minio", "caddy", "uptime-kuma", "web"} <= names
    assert set(SERVICES) <= names
    assert "models" not in names
    for svc in SERVICES:
        assert cfg["services"][svc]["build"]["dockerfile"].endswith(f"{svc}.Dockerfile")
        assert Path(cfg["services"][svc]["build"]["context"]).resolve() == REPO_ROOT
        assert "healthcheck" in cfg["services"][svc]


@needs_docker
def test_compose_gpu_profile_serves_single_model() -> None:
    cfg = _compose_config(COMPOSE_BASE, profiles=("gpu",))
    models = cfg["services"]["models"]
    assert "build" not in models
    assert models["image"].startswith("vllm/vllm-openai")
    devices = models["deploy"]["resources"]["reservations"]["devices"]
    assert devices[0]["capabilities"] == ["gpu"]
    assert "vision" in cfg["services"]


@needs_docker
def test_compose_dev_overlay() -> None:
    cfg = _compose_config(COMPOSE_BASE, COMPOSE_DEV)
    services = cfg["services"]
    assert "caddy" not in services and "uptime-kuma" not in services
    api = services["api"]
    assert any(str(p.get("published")) == "8000" for p in api["ports"])
    # compose resolves bind sources to absolute paths (backslashes on Windows).
    sources = [v.get("source", "").replace("\\", "/") for v in api["volumes"]]
    assert any(src.endswith("/services/api") for src in sources), sources
    command = " ".join(api["command"])
    assert "/app/serve.py ctcv_api 8000" in command and "--reload" in command
    assert services["web"]["environment"]["VITE_API_BASE"].endswith("/v1")


@needs_docker
@pytest.mark.parametrize("profile", ["gpu", "cpu"])
def test_compose_prod_overlay(profile: str) -> None:
    cfg = _compose_config(COMPOSE_BASE, COMPOSE_PROD, profiles=(profile,))
    services = cfg["services"]
    assert {"prometheus", "grafana", "alertmanager", "caddy", "uptime-kuma"} <= set(services)
    assert ("models" in services) == (profile == "gpu")
    assert ("dcgm-exporter" in services) == (profile == "gpu")
    for svc in (*SERVICES, "web", "caddy"):
        assert services[svc]["restart"] == "unless-stopped", svc
        logging = services[svc]["logging"]
        assert logging["driver"] == "json-file" and "max-size" in logging["options"]
        assert services[svc]["deploy"]["resources"]["limits"]["memory"]
    assert "DNS-only" in COMPOSE_PROD.read_text(encoding="utf-8"), "ETH-12 note"


@needs_docker
def test_compose_ci_overlay_adds_gha_cache() -> None:
    cfg = _compose_config(COMPOSE_BASE, COMPOSE_CI)
    for svc in (*SERVICES, "web"):
        build = cfg["services"][svc]["build"]
        assert any("type=gha" in c for c in build["cache_from"])
        assert any("type=gha" in c for c in build["cache_to"])


# --------------------------------------------------------------------------- dockerfiles
@pytest.mark.parametrize("svc", SERVICES)
def test_python_dockerfile_contract(svc: str) -> None:
    text = (DEPLOY / "docker" / f"{svc}.Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim" in text
    assert "COPY --from=ghcr.io/astral-sh/uv:" in text
    assert f"--package ctcv-{svc}" in text and "--frozen" in text and "--no-dev" in text
    assert "--no-editable" in text, "fallback to --no-editable required"
    assert re.search(r"^USER\s+\S+", text, re.MULTILINE)
    assert "HEALTHCHECK" in text and "/health" in text
    # CMD: the spec form is documented, serve.py resolves the real ASGI target at start.
    assert f"uvicorn ctcv_{svc}.main:app --host 0.0.0.0 --port {PORTS[svc]}" in text
    assert f'CMD ["python", "/app/serve.py", "ctcv_{svc}", "{PORTS[svc]}"]' in text


def _normalized_dockerfile(svc: str) -> str:
    text = (DEPLOY / "docker" / f"{svc}.Dockerfile").read_text(encoding="utf-8")
    text = re.sub(r'^ARG APT_PACKAGES=".*"$', 'ARG APT_PACKAGES="<apt>"', text, flags=re.M)
    text = re.sub(r"--start-period=\d+s", "--start-period=<n>s", text)
    for token in (f"ctcv-{svc}", f"ctcv_{svc}", f"# CTCV {svc} service", f"build {svc}"):
        text = text.replace(token, token.replace(svc, "<svc>"))
    text = text.replace(f"COPY services/{svc} services/{svc}", "COPY services/<svc> services/<svc>")
    return text.replace(str(PORTS[svc]), "<port>")


def test_python_dockerfiles_are_consistent() -> None:
    """The four service Dockerfiles differ only in name, port, APT packages, start period."""
    reference = _normalized_dockerfile("api")
    for svc in SERVICES[1:]:
        assert _normalized_dockerfile(svc) == reference, svc
    assert "\\\n" in reference, "line continuations must be real (not collapsed)"


def test_web_dockerfile_contract() -> None:
    text = (DEPLOY / "docker" / "web.Dockerfile").read_text(encoding="utf-8")
    assert "node:20-alpine" in text and "caddy:2-alpine" in text and "pnpm" in text
    caddyfile = (DEPLOY / "caddy" / "Caddyfile.web").read_text(encoding="utf-8")
    assert "reverse_proxy" in caddyfile and "api:8000" in caddyfile
    assert "try_files" in caddyfile and "/index.html" in caddyfile


def test_prod_caddyfile_contract() -> None:
    text = (DEPLOY / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    assert "{$APP_DOMAIN" in text and "{$STATUS_DOMAIN" in text
    assert "uptime-kuma:3001" in text
    assert "Strict-Transport-Security" in text and "X-Content-Type-Options" in text


# --------------------------------------------------------------------------- monitoring
def test_prometheus_config_and_rules() -> None:
    prom = yaml.safe_load((DEPLOY / "monitoring" / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = {job["job_name"] for job in prom["scrape_configs"]}
    assert {"api", "agent", "speech", "vision", "models"} <= jobs
    rules = yaml.safe_load((DEPLOY / "monitoring" / "alert-rules.yml").read_text(encoding="utf-8"))
    alerts = {r["alert"] for g in rules["groups"] for r in g["rules"]}
    assert {"HighP95Latency", "HighErrorRate", "GpuMemoryHigh", "ServiceDown"} <= alerts
    by_name = {r["alert"]: r for g in rules["groups"] for r in g["rules"]}
    assert by_name["HighP95Latency"]["for"] == "5m" and "> 3" in by_name["HighP95Latency"]["expr"]
    assert "0.02" in by_name["HighErrorRate"]["expr"]
    assert "0.92" in by_name["GpuMemoryHigh"]["expr"]


def test_grafana_provisioning() -> None:
    prov = DEPLOY / "monitoring" / "grafana" / "provisioning"
    ds = yaml.safe_load((prov / "datasources" / "datasource.yml").read_text(encoding="utf-8"))
    assert ds["datasources"][0]["type"] == "prometheus"
    dash = json.loads(
        (DEPLOY / "monitoring" / "grafana" / "dashboards" / "ctcv-overview.json").read_text(
            encoding="utf-8"
        )
    )
    titles = " ".join(p["title"].lower() for p in dash["panels"])
    for needle in ("p95", "gpu", "escalate", "5xx"):
        assert needle in titles, needle


def test_readmes_exist() -> None:
    for rel in (
        "README.md",
        "models/README.md",
        "models/vllm.env.example",
        "status/README.md",
        "monitoring/uptime-kuma/README.md",
    ):
        assert (DEPLOY / rel).is_file(), rel


def test_models_readme_and_env_example() -> None:
    readme = (DEPLOY / "models" / "README.md").read_text(encoding="utf-8")
    for flag in ("--model", "Qwen/Qwen3.5-9B", "--max-model-len", "--gpu-memory-utilization"):
        assert flag in readme, flag
    assert "awq" in readme.lower() and "--enable-lora" in readme
    example = (DEPLOY / "models" / "vllm.env.example").read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0] for line in example.splitlines() if "=" in line and line[0] != "#"
    }
    compose = COMPOSE_BASE.read_text(encoding="utf-8")
    for key in sorted(set(re.findall(r"\$\$\{(VLLM_[A-Z_]+|LLAMA_[A-Z_]+)", compose))):
        assert key in keys, f"{key} used by docker-compose.yml is missing from vllm.env.example"
    assert "CHANGE_ME" not in example or "HF_TOKEN" in example


def test_deploy_readme_covers_runbook() -> None:
    text = (DEPLOY / "README.md").read_text(encoding="utf-8")
    for needle in (
        "make dev",
        "make deploy ENV=staging",
        "make rollback TAG=",
        "make failover",
        "make backup",
        "make restore-drill",
        "self-hosted",
        "T-72h",
        "T-48h",
        "DNS-only",
    ):
        assert needle in text, needle


# --------------------------------------------------------------------------- workflows
def _load_workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_workflow_files() -> None:
    names = {p.name for p in WORKFLOWS.glob("*.yml")}
    assert {"check.yml", "gate.yml", "release.yml"} <= names
    assert "nightly-eval.yml" not in names, "superseded by gate.yml"


def test_check_workflow_is_deterministic() -> None:
    wf = _load_workflow("check.yml")
    triggers = wf[True] if True in wf else wf["on"]
    assert "pull_request" in triggers and "push" in triggers
    assert {"check", "e2e", "build", "audit"} <= set(wf["jobs"])
    text = (WORKFLOWS / "check.yml").read_text(encoding="utf-8")
    assert "make check QUICK=1" in text and "make e2e E2E=1" in text
    assert "--profile cpu build" in text and "gitleaks/gitleaks-action" in text
    for forbidden in ("claude -p", "ANTHROPIC_API_KEY", "make gate", "make eval"):
        assert forbidden not in text, f"check.yml must never call a model ({forbidden})"
    assert "playwright-report" in text and "eval/reports" in text
    assert "workflow_call" in triggers, "release.yml reuses check.yml"
    assert all(job["runs-on"] == "ubuntu-latest" for job in wf["jobs"].values())


def test_gate_workflow_needs_gpu_runner() -> None:
    wf = _load_workflow("gate.yml")
    triggers = wf[True] if True in wf else wf["on"]
    assert triggers["schedule"][0]["cron"] == "0 19 * * *"
    assert "workflow_dispatch" in triggers and "pull_request" in triggers
    job = next(iter(wf["jobs"].values()))
    assert job["runs-on"] == ["self-hosted", "gpu"]
    text = (WORKFLOWS / "gate.yml").read_text(encoding="utf-8")
    assert "make gate" in text and "needs-gpu" in text
    assert "git commit" not in text and "git push" not in text


def test_release_workflow_builds_and_deploys() -> None:
    wf = _load_workflow("release.yml")
    triggers = wf[True] if True in wf else wf["on"]
    assert triggers["push"]["tags"] == ["v*"]
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "ghcr.io/${{ github.repository_owner }}/ctcv-" in text
    assert "deploy/scripts/deploy.sh" in text
    assert "DEPLOY_HOST" in text and "SSH_KEY" in text
    assert wf["jobs"]["check"]["uses"] == "./.github/workflows/check.yml"
    assert set(wf["jobs"]["images"]["strategy"]["matrix"]["svc"]) == {*SERVICES, "web"}
    assert "images" in wf["jobs"]["deploy"]["needs"]


def test_github_meta_files() -> None:
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    for heading in ("Làm gì", "Test thế nào", "Checklist", "Rủi ro"):
        assert heading in template
    assert template.count("- [ ]") >= 8, "DoD checklist from plan Appendix B"
    bot = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {u["package-ecosystem"] for u in bot["updates"]}
    assert {"uv", "npm", "docker", "github-actions"} <= ecosystems
    assert all(u["schedule"]["interval"] == "weekly" for u in bot["updates"])

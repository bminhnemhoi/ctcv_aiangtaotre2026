from __future__ import annotations

from pathlib import Path

import doctor
import pytest

HAPPY: dict[str, tuple[int, str]] = {
    "uv --version": (0, "uv 0.10.9"),
    "uv python find": (0, "C:/py/python.exe"),
    "node --version": (0, "v24.14.1"),
    "pnpm --version": (0, "12.4.2"),
    "docker info": (0, "29.5.3"),
    "make --version": (0, "GNU Make 4.4.1"),
    "gitleaks version": (0, "8.30.1"),
    "ruff --version": (0, "ruff 0.16.8"),
    "pre-commit --version": (0, "pre-commit 4.6.2"),
    "git -C": (0, "true"),
    "nvidia-smi": (127, "không tìm thấy lệnh"),
}


def make_runner(overrides: dict[str, tuple[int, str]] | None = None, git_identity: bool = True):
    table = {**HAPPY, **(overrides or {})}

    def run(cmd: list[str]) -> tuple[int, str]:
        joined = " ".join(cmd)
        if "config user.name" in joined:
            return (0, "Đội CTCV") if git_identity else (1, "")
        if "config user.email" in joined:
            return (0, "ctcv@example.com") if git_identity else (1, "")
        for prefix, result in table.items():
            if joined.startswith(prefix):
                return result
        return 127, "không tìm thấy lệnh"

    return run


def _by_name(checks: list[doctor.Check]) -> dict[str, doctor.Check]:
    return {c.name: c for c in checks}


def test_happy_path_no_hard_failures(docs_root: Path) -> None:
    checks = doctor.run_all(docs_root, make_runner())
    assert doctor.hard_failures(checks) == []
    rows = _by_name(checks)
    assert rows["uv"].status == "OK"
    assert rows["Python 3.12"].status == "OK"
    assert rows["node"].status == "OK"
    assert rows["Docker"].status == "OK"
    assert rows["git"].status == "OK"
    assert rows["GPU"].status == "INFO"
    assert rows["DNS"].status == "INFO"
    assert rows[".env"].status == "WARN"  # no .env in the fixture
    assert rows["HF_TOKEN"].status == "WARN"


def test_missing_uv_and_docs_are_hard_failures(tmp_path: Path) -> None:
    checks = doctor.run_all(
        tmp_path, make_runner({"uv --version": (127, ""), "uv python find": (127, "")})
    )
    names = {c.name for c in doctor.hard_failures(checks)}
    assert "uv" in names
    assert "docs/idea.md" in names
    assert "docs/template/AI2026_Mau_ho_so.docx" in names


def test_python_falls_back_to_running_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    run = make_runner({"uv python find": (1, "")})
    monkeypatch.setattr(doctor.sys, "version_info", (3, 12, 6, "final", 0))
    assert doctor.check_python(run).status == "OK"
    monkeypatch.setattr(doctor.sys, "version_info", (3, 14, 0, "final", 0))
    check = doctor.check_python(run)
    assert check.status == "FAIL" and check.hard


def test_old_node_and_missing_pnpm_warn() -> None:
    run = make_runner({"node --version": (0, "v18.2.0"), "pnpm --version": (127, "")})
    assert doctor.check_versioned_tool(run, "node", 20, "h").status == "WARN"
    assert doctor.check_versioned_tool(run, "pnpm", 10, "h").status == "WARN"


def test_make_hint_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    run = make_runner({"make --version": (127, "")})
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    assert "winget" in doctor.check_make(run).detail
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    assert "winget" not in doctor.check_make(run).detail


def test_env_file_missing_keys_never_prints_values(docs_root: Path) -> None:
    (docs_root / ".env").write_text("A=secret-value-123\n", encoding="utf-8")
    check = doctor.check_env_file(docs_root)
    assert check.status == "WARN"
    assert "B" in check.detail and "HF_TOKEN" in check.detail
    assert "secret-value-123" not in check.detail
    (docs_root / ".env").write_text("A=1\nB=2\nHF_TOKEN=hf_x\n", encoding="utf-8")
    assert doctor.check_env_file(docs_root).status == "OK"
    assert doctor.check_hf_token(docs_root).status == "OK"


def test_git_without_identity_warns(docs_root: Path) -> None:
    assert doctor.check_git(make_runner(git_identity=False), docs_root).status == "WARN"
    assert doctor.check_git(make_runner({"git -C": (128, "")}), docs_root).status == "WARN"


def test_dns_resolution(docs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DOMAIN", "app.example.org")
    assert "1.2.3.4" in doctor.check_dns(docs_root, resolve=lambda d: "1.2.3.4").detail

    def boom(_: str) -> str:
        raise OSError("nx")

    assert "chưa phân giải" in doctor.check_dns(docs_root, resolve=boom).detail
    monkeypatch.setenv("APP_DOMAIN", "localhost")
    assert "bỏ qua" in doctor.check_dns(docs_root).detail


def test_main_exit_codes(
    docs_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(doctor, "run_command", make_runner())
    assert doctor.main(["--root", str(docs_root)]) == 0
    assert "DOCTOR OK" in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert doctor.main(["--root", str(empty)]) == 1
    assert "bắt buộc chưa đạt" in capsys.readouterr().out


def test_run_command_handles_missing_binary() -> None:
    code, out = doctor.run_command(["definitely-not-a-real-binary-ctcv"])
    assert code == 127
    assert out


def test_gpu_host_checks(docs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GPU_SSH_HOST", raising=False)
    assert doctor.check_gpu_host(make_runner(), docs_root)[0].status == "WARN"
    monkeypatch.setenv("GPU_SSH_HOST", "gpu.example.org")
    rows = doctor.check_gpu_host(make_runner({"ssh -o": (255, "")}), docs_root)
    assert rows[0].status == "WARN" and "gpu.example.org" in rows[0].detail

    def run(cmd: list[str]) -> tuple[int, str]:
        return (
            (0, "NVIDIA RTX 4090, 24564 MiB") if "nvidia-smi" in cmd else (0, "Docker version 29")
        )

    rows = doctor.check_gpu_host(run, docs_root)
    assert [r.status for r in rows] == ["OK", "OK"]
    assert "RTX 4090" in rows[0].detail
    assert (
        len(doctor.run_all(docs_root, make_runner(), gpu=True))
        == len(doctor.run_all(docs_root, make_runner())) + 1
    )

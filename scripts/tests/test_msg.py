from __future__ import annotations

import msg
import pytest


def test_render_with_args() -> None:
    assert msg.render("not-implemented", ["E12"]) == "CHƯA HIỆN THỰC — xem epics/E12.md"
    assert msg.render("check-green", ["1"]).endswith("(QUICK=1)")


def test_every_message_is_vietnamese_and_short() -> None:
    for key, text in msg.MESSAGES.items():
        assert key == key.lower() and " " not in key
        assert 0 < len(text) < 200


def test_main_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert msg.main(["gitleaks-clean"]) == 0
    assert capsys.readouterr().out.strip() == "gitleaks: sạch"
    assert msg.main([]) == 2
    assert msg.main(["no-such-key"]) == 2
    assert msg.main(["not-implemented"]) == 2  # missing argument

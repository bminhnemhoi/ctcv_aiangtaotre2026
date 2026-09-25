from __future__ import annotations

import pytest

from ctcv_core.errors import AppError, Forbidden, NotFound, NotImplementedYet, ValidationFailed


def test_app_error_fields_and_response() -> None:
    err = AppError("SCENARIO_NOT_FOUND", "Không tìm thấy bài học này, bác thử chọn bài khác nhé.")
    assert err.code == "SCENARIO_NOT_FOUND"
    assert err.status == 400
    assert err.details is None
    assert err.to_response() == {
        "error": {
            "code": "SCENARIO_NOT_FOUND",
            "message": "Không tìm thấy bài học này, bác thử chọn bài khác nhé.",
        }
    }
    assert str(err) == "SCENARIO_NOT_FOUND: Không tìm thấy bài học này, bác thử chọn bài khác nhé."
    assert "SCENARIO_NOT_FOUND" in repr(err)


def test_app_error_with_status_and_details() -> None:
    err = AppError("RATE_LIMITED", "Bác chờ một chút rồi thử lại nhé.", 429, {"retry_after": 5})
    assert err.status == 429
    assert err.to_response()["error"]["details"] == {"retry_after": 5}


def test_empty_details_not_serialised() -> None:
    err = AppError("X", "y", details={})
    assert "details" not in err.to_response()["error"]


@pytest.mark.parametrize(
    ("cls", "status", "code"),
    [
        (NotImplementedYet, 501, "NOT_IMPLEMENTED"),
        (NotFound, 404, "NOT_FOUND"),
        (Forbidden, 403, "FORBIDDEN"),
        (ValidationFailed, 422, "VALIDATION_FAILED"),
    ],
)
def test_subclass_defaults(cls: type[AppError], status: int, code: str) -> None:
    err = cls()
    assert isinstance(err, AppError)
    assert err.status == status
    assert err.code == code
    assert err.message_vi
    assert err.to_response()["error"]["code"] == code


def test_subclass_custom_message_and_code() -> None:
    err = NotFound("Không tìm thấy lớp học này.", code="CLASS_NOT_FOUND", details={"class_id": "x"})
    assert err.status == 404
    assert err.code == "CLASS_NOT_FOUND"
    assert err.message_vi == "Không tìm thấy lớp học này."
    assert err.to_response()["error"]["details"] == {"class_id": "x"}


def test_is_raisable() -> None:
    with pytest.raises(AppError) as info:
        raise ValidationFailed()
    assert info.value.status == 422

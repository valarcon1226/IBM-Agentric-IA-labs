from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import ReviewRequest, StatusResponse


def test_status_response_has_documented_counts():
    result = StatusResponse(
        upload_id=uuid4(),
        status="completed",
        total_rows=3,
        clean_rows=1,
        ambiguous_rows=1,
        failed_rows=1,
    )
    assert result.model_dump()["clean_rows"] == 1


def test_review_action_is_limited_to_approve_or_reject():
    with pytest.raises(ValidationError):
        ReviewRequest(record_id=uuid4(), action="erase")

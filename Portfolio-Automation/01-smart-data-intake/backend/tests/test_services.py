import pytest

from app.services import clean_row, normalize_row, row_issues


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1-555-0198",
                "company": "Acme Corp",
            },
            "clean",
        ),
        (
            {
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@smith",
                "phone": "555-0199",
                "company": "",
            },
            "ambiguous",
        ),
        (
            {
                "first_name": " ",
                "last_name": " ",
                "email": "invalid-email",
                "phone": "",
                "company": "",
            },
            "failed",
        ),
    ],
)
def test_readme_sample_rows(row, expected):
    assert clean_row(row) == expected


def test_ambiguous_reasons_and_normalization():
    row = {
        "first_name": " Jane ",
        "last_name": " Smith ",
        "email": " JANE@SMITH ",
        "phone": "555-0199",
        "company": " ",
    }
    assert normalize_row(row)["email"] == "jane@smith"
    assert row_issues(row) == ["Missing company", "Potentially invalid email domain"]

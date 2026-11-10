import pytest

from app.normalization import normalize_email, normalize_name, normalize_phone, normalize_website


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(601) 234-5678", "+576012345678"),  # parens/dash, implicit country
        ("301-234-5679", "+573012345679"),  # dashed mobile, no country code
        ("+57 300 234 5680", "+573002345680"),  # spaced, with country code
        ("3012345678", "+573012345678"),  # plain digits, no country code
        ("601 234 5678", "+576012345678"),  # space-separated landline
        ("+573002345680", "+573002345680"),  # compact, with country code
        ("3012345678 ext. 102", "+573012345678"),  # extension is parsed, not in E.164
    ],
)
def test_normalize_phone_colombian_formats(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_phone_old_landline_format_is_now_upgraded():
    assert normalize_phone("(1) 345-6781") == "+576013456781"
    assert normalize_phone("+57 1 456 7890") == "+576014567890"
    assert normalize_phone("1 3456781") == "+576013456781"


@pytest.mark.parametrize("raw", [None, "", "abc", "123"])
def test_normalize_phone_invalid_or_missing_returns_none(raw):
    assert normalize_phone(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Contadores Ruiz SAS", "contadores ruiz"),
        ("Contadores Ruiz S.A.S.", "contadores ruiz"),
        ("Restaurante Doña Rosa", "restaurante dona rosa"),
        ("Clínica Dental Avanzada Ltda.", "clinica dental avanzada"),
        ("Clínica Dental Avanzada LTDA", "clinica dental avanzada"),
        ("  Múltiples   Espacios  ", "multiples espacios"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_normalize_email():
    assert normalize_email("  Info@Empresa.COM  ") == "info@empresa.com"
    assert normalize_email(None) is None
    assert normalize_email("") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.Empresa.com/", "empresa.com"),
        ("http://empresa.com", "empresa.com"),
        ("empresa.com/", "empresa.com"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_website(raw, expected):
    assert normalize_website(raw) == expected

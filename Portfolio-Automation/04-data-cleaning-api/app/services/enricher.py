import logging
import re
from email.utils import parseaddr

import pandas as pd
import phonenumbers

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_emails(df: pd.DataFrame, email_column: str) -> pd.DataFrame:
    df_enriched = df.copy()

    def is_valid_email(email):
        if pd.isna(email):
            return False
        _, parsed = parseaddr(str(email).strip())
        return bool(EMAIL_REGEX.match(parsed)) if parsed else False

    df_enriched["email_valid"] = df_enriched[email_column].apply(is_valid_email)
    return df_enriched


def normalize_phones(
    df: pd.DataFrame, phone_column: str, default_region: str = "US"
) -> pd.DataFrame:
    df_enriched = df.copy()

    def process_phone(phone_str):
        if pd.isna(phone_str):
            return pd.Series([None, False])
        try:
            parsed = phonenumbers.parse(str(phone_str), default_region)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                return pd.Series([e164, True])
            return pd.Series([str(phone_str), False])
        except phonenumbers.NumberParseException:
            return pd.Series([str(phone_str), False])

    df_enriched[["phone_e164", "phone_valid"]] = df_enriched[phone_column].apply(process_phone)
    return df_enriched

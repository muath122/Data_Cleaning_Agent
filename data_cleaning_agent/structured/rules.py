"""Deterministic rules: uncertainty returns the original value plus a review rule."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from numbers import Integral, Real

from .normalizers import (
    AR_LEVEL_WORDS,
    ATTENDANCE_MAP,
    BOOLEAN_MAP,
    GENDER_MAP,
    blank,
    text,
)


@dataclass
class Normalized:
    value: object
    issue: str | None = None


def numeric_text(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return str(value)
    if isinstance(value, Real):
        if not float(value).is_integer() or abs(value) > 2**53:
            return None
        return str(int(value))
    return text(value)


def phone(value):
    s = numeric_text(value)
    if s is None:
        return Normalized(value, "invalid_phone")

   
    s = str(s).translate(
        str.maketrans(
            "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
            "01234567890123456789",
        )
    )
    s = re.sub(r"[\s\-\(\)\.]", "", s)

    
    if re.fullmatch(r"\+9665[0-9]{8}", s):
        return Normalized("0" + s[4:])

    
    if re.fullmatch(r"009665[0-9]{8}", s):
        return Normalized("0" + s[5:])
    if re.fullmatch(r"9665[0-9]{8}", s):
        return Normalized("0" + s[3:])

   
    if re.fullmatch(r"05[0-9]{8}", s):
        return Normalized(s)


    if re.fullmatch(r"5[0-9]{8}", s):
        return Normalized("0" + s)

   
    return Normalized(value, "unsupported_or_invalid_phone")




def email(value):
    if not isinstance(value, str):
        return Normalized(value, "invalid_email")
    s = value.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", s):
        return Normalized(value, "invalid_email")
    local, domain = s.rsplit("@", 1)
    # The local part may be case-sensitive; do not remove embedded whitespace.
    return Normalized(local + "@" + domain.casefold())


def mapped(value, table, issue):
    key = text(value).casefold().replace("ـ", "")
    if key in table:
        return Normalized(table[key])
    return Normalized(value, issue)


def university_id(value):
    s = numeric_text(value)
    if s is None or not re.fullmatch(r"[A-Za-z0-9]+", s):
        return Normalized(value, "invalid_university_id")
    # Do not invent leading digits or change case of an alphanumeric identifier.
    return Normalized(
        s, "numeric_identifier_requires_review" if not isinstance(value, str) else None
    )


def academic_level(value):
    s = numeric_text(value)
    if s is None:
        return Normalized(value, "ambiguous_academic_level")
    s = s.casefold().replace("ـ", "")
    match = re.fullmatch(r"(?:(?:level|lvl|l|المستوى)\s*)?(1[0-2]|[1-9])", s)
    if match:
        return Normalized(f"Level {int(match.group(1))}")
    ordinal = re.sub(r"^المستوى\s+", "", s)
    if ordinal in AR_LEVEL_WORDS:
        return Normalized(f"Level {AR_LEVEL_WORDS[ordinal]}")
    # Year of study is not assumed to equal academic level/semester.
    return Normalized(value, "ambiguous_academic_level")


def timestamp(value):
    if isinstance(value, (datetime, date)):
        return Normalized(
            value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
        )
    if not isinstance(value, str):
        return Normalized(value, "ambiguous_timestamp")
    s = text(value)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[ T].+)?", s):
        return Normalized(value, "ambiguous_timestamp")
    try:
        parsed = (
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            if len(s) > 10
            else date.fromisoformat(s)
        )
        return Normalized(
            parsed.isoformat(sep=" ") if isinstance(parsed, datetime) else parsed.isoformat()
        )
    except ValueError:
        return Normalized(value, "invalid_timestamp")


def boolean(value):
    s = numeric_text(value)
    if isinstance(value, bool):
        return Normalized(value)
    if s is not None and s.casefold() in BOOLEAN_MAP:
        return Normalized(BOOLEAN_MAP[s.casefold()])
    return Normalized(value, "unknown_boolean")


def attendance(value):
    binary = boolean(value)
    if binary.issue is None:
        return Normalized("Present" if binary.value else "Absent")
    return mapped(value, ATTENDANCE_MAP, "unknown_attendance")


RULES = {
    "phone": phone,
    "email": email,
    "gender": lambda value: mapped(value, GENDER_MAP, "unknown_gender"),
    "university_id": university_id,
    "academic_level": academic_level,
    "timestamp": timestamp,
    "attendance": attendance,
    "boolean": boolean,
}


def normalize_value(value, role):
    if blank(value):
        return Normalized(value)
    return RULES[role](value)

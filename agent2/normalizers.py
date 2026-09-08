import datetime
import re

import numpy as np
import pandas as pd


ARABIC_TO_WESTERN_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789",
)


def blank(value):
    return pd.isna(value) or (
        isinstance(value, str) and not value.strip()
    )


def text(value):
    if blank(value):
        return value
    return re.sub(
        r"\s+",
        " ",
        str(value)
        .translate(ARABIC_TO_WESTERN_DIGITS)
        .strip(),
    )


def header_key(column):
    """
    Used only to recognize a supported role after Agent 1.
    Agent 2 does not rename columns.
    """
    value = (
        str(column)
        .strip()
        .casefold()
        .replace("_", " ")
        .replace("-", " ")
    )
    return re.sub(r"\s+", " ", value)


ROLE_ALIASES = {
    "phone": {
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "رقم الجوال",
        "الجوال",
        "رقم الهاتف",
    },
    "email": {
        "email",
        "e mail",
        "email address",
        "البريد الالكتروني",
        "البريد الإلكتروني",
    },
    "gender": {
        "gender",
        "sex",
        "الجنس",
    },
    "university_id": {
        "university id",
        "student id",
        "university number",
        "student number",
        "الرقم الجامعي",
        "رقم جامعي",
    },
    "university": {
        "university",
        "university name",
        "institution",
        "institution name",
        "الجامعة",
        "اسم الجامعة",
    },
    "academic_level": {
        "academic level",
        "level",
        "study level",
        "المستوى الاكاديمي",
        "المستوى الأكاديمي",
        "المستوى",
    },
    "timestamp": {
        "timestamp",
        "date time",
        "datetime",
        "submission time",
        "submitted at",
        "التاريخ والوقت",
        "وقت الارسال",
        "وقت الإرسال",
    },
    "attendance": {
        "attendance",
        "attendance status",
        "الحضور",
        "حالة الحضور",
    },
    "boolean": {
        "boolean",
        "yes no",
        "true false",
    },
}


def infer_supported_role(column):
    key = header_key(column)
    for role, aliases in ROLE_ALIASES.items():
        if key in aliases:
            return role
    return None


def normalize_phone(value):
    if blank(value):
        return value

    s = text(value)
    s = re.sub(r"\.0+$", "", s)
    s = re.sub(r"[\s\-()]", "", s)

    if s.startswith("00966"):
        s = "+966" + s[5:]
    elif s.startswith("966"):
        s = "+" + s
    elif re.fullmatch(r"05\d{8}", s):
        s = "+966" + s[1:]
    elif re.fullmatch(r"5\d{8}", s):
        s = "+966" + s

    return s


def normalize_email(value):
    if blank(value):
        return value
    return text(value).replace(" ", "").casefold()


GENDER_MAP = {
    "male": "Male",
    "m": "Male",
    "man": "Male",
    "ذكر": "Male",
    "رجل": "Male",
    "female": "Female",
    "f": "Female",
    "woman": "Female",
    "انثى": "Female",
    "أنثى": "Female",
    "امرأة": "Female",
    "امراه": "Female",
}


def normalize_gender(value):
    if blank(value):
        return value

    s = text(value)
    key = s.casefold().replace("ـ", "")
    return GENDER_MAP.get(key, s)


def normalize_university_id(value):
    """
    University/student ID only.
    This is separate from national-ID handling.
    """
    if blank(value):
        return value

    s = text(value)
    s = re.sub(r"\.0+$", "", s)
    s = re.sub(r"\s+", "", s)
    return s.upper()


AR_LEVEL_WORDS = {
    "الاول": 1,
    "الأول": 1,
    "اول": 1,
    "الثاني": 2,
    "ثاني": 2,
    "الثالث": 3,
    "ثالث": 3,
    "الرابع": 4,
    "رابع": 4,
    "الخامس": 5,
    "خامس": 5,
    "السادس": 6,
    "سادس": 6,
    "السابع": 7,
    "سابع": 7,
    "الثامن": 8,
    "ثامن": 8,
    "التاسع": 9,
    "تاسع": 9,
    "العاشر": 10,
    "عاشر": 10,
}


def normalize_academic_level(value):
    if blank(value):
        return value

    s = text(value)
    low = s.casefold().replace("ـ", "")

    match = re.search(
        r"(?:level|lvl|l|year|المستوى)?\s*([1-9]|10)\b",
        low,
    )
    if match:
        return f"Level {int(match.group(1))}"

    for word, number in AR_LEVEL_WORDS.items():
        if word in low:
            return f"Level {number}"

    return s


def normalize_timestamp(value):
    if blank(value):
        return value

    try:
        dt = pd.to_datetime(value, errors="raise")
        if pd.isna(dt):
            return value
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return text(value)


ATTENDANCE_MAP = {
    "present": "Present",
    "attended": "Present",
    "حاضر": "Present",
    "حضرت": "Present",
    "نعم": "Present",
    "yes": "Present",
    "absent": "Absent",
    "غياب": "Absent",
    "غائب": "Absent",
    "لم يحضر": "Absent",
    "لا": "Absent",
    "no": "Absent",
    "late": "Late",
    "متأخر": "Late",
    "متاخر": "Late",
    "excused": "Excused",
    "excused absence": "Excused",
    "بعذر": "Excused",
    "غياب بعذر": "Excused",
}


def normalize_attendance(value):
    if blank(value):
        return value

    s = text(value)
    return ATTENDANCE_MAP.get(s.casefold(), s)


BOOLEAN_MAP = {
    "true": True,
    "yes": True,
    "y": True,
    "1": True,
    "نعم": True,
    "صح": True,
    "صحيح": True,
    "false": False,
    "no": False,
    "n": False,
    "0": False,
    "لا": False,
    "خطأ": False,
    "خطا": False,
}


def normalize_boolean(value):
    if blank(value):
        return value

    s = text(value)
    return BOOLEAN_MAP.get(s.casefold(), value)


NORMALIZERS = {
    "phone": normalize_phone,
    "email": normalize_email,
    "gender": normalize_gender,
    "university_id": normalize_university_id,
    "academic_level": normalize_academic_level,
    "timestamp": normalize_timestamp,
    "attendance": normalize_attendance,
    "boolean": normalize_boolean,
}


def looks_boolean_series(series):
    values = [
        str(text(v)).casefold()
        for v in series.dropna().head(200)
        if not blank(v)
    ]

    if not values:
        return False

    known = set(BOOLEAN_MAP)

    return (
        len(set(values)) <= 6
        and sum(v in known for v in values) / len(values) >= 0.90
    )


def standardize_structure(df):
    """
    Apply Agent 2's structured-column standardization.
    Unknown/unrelated columns are preserved unchanged.
    """
    out = df.copy(deep=True)
    report = []

    for column in out.columns:
        role = infer_supported_role(column)

        if role is None and looks_boolean_series(out[column]):
            role = "boolean"

        # University is handled in a second cross-file pass.
        if role == "university":
            continue

        if role is None:
            continue

        before = out[column].copy()
        out[column] = out[column].map(NORMALIZERS[role])

        changed = int(
            (
                before.fillna("<NA>").astype(str)
                != out[column].fillna("<NA>").astype(str)
            ).sum()
        )

        report.append(
            {
                "Column": column,
                "Role": role,
                "Values Changed": changed,
            }
        )

    return out, report

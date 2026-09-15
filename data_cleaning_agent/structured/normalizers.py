"""Structured-field aliases from Amirah's PR #4, with conservative normalization."""

import re

import pandas as pd

ARABIC_TO_WESTERN_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


def blank(value):
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def text(value):
    if blank(value):
        return value
    return re.sub(
        r"\s+",
        " ",
        str(value).translate(ARABIC_TO_WESTERN_DIGITS).strip(),
    )


def header_key(column):
    """
    Used only to recognize a supported role after Agent 1.
    Agent 2 does not rename columns.
    """
    value = str(column).strip().casefold().replace("_", " ").replace("-", " ")
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
        "personal email",
        "university email",
        "gmail",
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
    key = re.sub(r" [0-9]+$", "", header_key(column))
    for role, aliases in ROLE_ALIASES.items():
        if key in aliases:
            return role
    return None


GENDER_MAP = {
    "male": "Male",
    "m": "Male",
    "man": "Male",
    "ذكر": "Male",
    "رجل": "Male",
    "male | رجل": "Male",
    "male|رجل": "Male",
    "female": "Female",
    "f": "Female",
    "woman": "Female",
    "انثى": "Female",
    "أنثى": "Female",
    "امرأة": "Female",
    "امراه": "Female",
    "female | أنثى": "Female",
    "female|أنثى": "Female",
}


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


def looks_categorical_series(series):
    """
    Detect whether a text column looks categorical.

    Formatting variants are considered the same category
    when estimating cardinality.
    """
    non_null = series.dropna()

    if non_null.empty:
        return False

    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False

    values = [text(value) for value in non_null if not blank(value)]

    if not values:
        return False

    keys = [categorical_key(value) for value in values]

    unique_count = len(set(keys))
    total_count = len(keys)
    unique_ratio = unique_count / total_count

    return unique_count <= 100 and unique_ratio <= 0.30


def categorical_key(value):
    """
    Create a comparison-only version of a categorical value.

    The key is used to discover formatting variants.
    It is NOT written into the final dataset.
    """
    if blank(value):
        return value

    s = text(value).casefold()

    s = s.replace("-", " ")
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def choose_canonical_value(values):
    """
    Choose the best representation from formatting variants.

    Preference:
    1. Most frequently occurring representation.
    2. If tied, prefer a naturally capitalized representation.
    3. Otherwise use the first observed representation.
    """
    counts = pd.Series(values).value_counts()
    highest_count = counts.max()

    candidates = [value for value, count in counts.items() if count == highest_count]

    if len(candidates) == 1:
        return candidates[0]

    for value in candidates:
        if value == value.title():
            return value

    return candidates[0]


def build_categorical_map(series):
    """
    Build a mapping for obvious formatting variants found
    inside a categorical column.

    No category names are hard-coded.
    """
    groups = {}

    for value in series.dropna():
        if blank(value):
            continue

        original = text(value)
        key = categorical_key(original)

        if key not in groups:
            groups[key] = []

        groups[key].append(original)

    mapping = {}

    for values in groups.values():
        unique_values = list(dict.fromkeys(values))

        if len(unique_values) <= 1:
            continue

        canonical = choose_canonical_value(values)

        for value in unique_values:
            if value != canonical:
                mapping[value] = canonical

    return mapping

"""Meaning-preserving local cleanup with opt-in legacy enrichment."""

import re

import pandas as pd
from textblob import TextBlob

from ..contracts import StageResult
from .categories import column_position

PLACEHOLDERS = {"-", ".", "لا يوجد", "لايوجد", "مافي", "none", "nan", "null", "لاشيء", "n/a", "na"}


def clean_text_basic(value, *, mask_pii=False):
    if pd.isna(value):
        return "", True
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in PLACEHOLDERS:
        return "", True
    return (mask_pii_locally(text) if mask_pii else text), False


def run_text(df, columns, *, enrich=False, mask_pii=False):
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Select at least one distinct text column")
    positions = [(column, column_position(df, column)) for column in columns]
    suffixes = ["cleaned", "missing"] + (["sentiment", "topics"] if enrich else [])
    generated = [f"{column}_{suffix}" for column in columns for suffix in suffixes]
    if len(generated) != len(set(generated)) or any(name in df.columns for name in generated):
        raise ValueError("Generated text columns already exist or conflict; choose another input")
    result = StageResult(df.copy(deep=True), "text")
    for column, position in positions:
        cleaned_values, missing_values = [], []
        for row, value in enumerate(df.iloc[:, position]):
            cleaned, missing = clean_text_basic(value, mask_pii=mask_pii)
            cleaned_values.append(cleaned)
            missing_values.append(missing)
            original = None if pd.isna(value) else str(value)
            if original != cleaned:
                result.changes.append(
                    {
                        "row_index": row,
                        "column_index": position,
                        "target_column": f"{column}_cleaned",
                        "before": original,
                        "after": cleaned,
                    }
                )
            if missing:
                result.issues.append(
                    {
                        "row_index": row,
                        "column_index": position,
                        "rule": "missing_or_placeholder",
                        "applicability": "unknown",
                    }
                )
        result.dataframe[f"{column}_cleaned"] = cleaned_values
        result.dataframe[f"{column}_missing"] = missing_values
        if enrich:
            result.dataframe[f"{column}_sentiment"] = [
                analyze_sentiment_locally(v) if v else "None" for v in cleaned_values
            ]
            result.dataframe[f"{column}_topics"] = [
                extract_local_topics(v) if v else "" for v in cleaned_values
            ]
    result.details = {
        "enrichment": enrich,
        "heuristic_pii_masking": mask_pii,
        "original_columns_retained": True,
        "fully_anonymized": False,
    }
    return result


POSITIVE_WORDS_AR = {
    "ممتاز",
    "رائع",
    "مفيد",
    "جميل",
    "استفدت",
    "شكرا",
    "شكراً",
    "قيمة",
    "تطوير",
    "مهارات",
    "فرصة",
    "اهتمام",
    "متحمس",
    "مبدع",
    "عظيم",
    "جيد",
    "التعرف",
    "ريادة",
}

NEGATIVE_WORDS_AR = {
    "سيء",
    "سيئ",
    "صعب",
    "ممل",
    "تشتت",
    "تضييع",
    "مشكلة",
    "ضعيف",
    "تحديات",
    "عقبات",
    "غير مفيد",
    "تأخير",
    "ازعاج",
}

STOPWORDS = {
    "من",
    "الى",
    "إلى",
    "عن",
    "على",
    "في",
    "كل",
    "مع",
    "هذا",
    "هذه",
    "التي",
    "الذي",
    "اللي",
    "كيفية",
    "and",
    "the",
    "in",
    "to",
    "for",
    "with",
    "is",
    "of",
    "it",
    "my",
    "i",
    "a",
    "an",
    "am",
    "very",
}


def mask_pii_locally(text: str) -> str:
    """Local Privacy Guard: Redact email, phone, and national ID."""
    if not text:
        return text
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    text = re.sub(email_pattern, "[EMAIL_REDACTED]", text)
    phone_pattern = r"(?:\+?966|0)?5\d{8}|\+?\d{10,14}"
    text = re.sub(phone_pattern, "[PHONE_REDACTED]", text)
    id_pattern = r"\b\d{10,}\b"
    text = re.sub(id_pattern, "[ID_REDACTED]", text)
    return text


def extract_local_topics(text: str) -> str:
    """Extract up to 3 distinct significant keywords locally."""
    words = re.findall(r"\b\w{3,}\b", str(text).lower())
    keywords = [w for w in words if w not in STOPWORDS]
    top_keys = list(dict.fromkeys(keywords))[:3]
    return ", ".join(top_keys) if top_keys else "general"


def analyze_sentiment_locally(text: str) -> str:
    """Rule-based Arabic sentiment classification and TextBlob polarity for English."""
    text_str = str(text)
    ar_pos = sum(1 for w in POSITIVE_WORDS_AR if w in text_str)
    ar_neg = sum(1 for w in NEGATIVE_WORDS_AR if w in text_str)

    if ar_pos > ar_neg:
        return "Positive"
    elif ar_neg > ar_pos:
        return "Negative"
    elif ar_pos > 0 and ar_pos == ar_neg:
        return "Mixed"

    try:
        polarity = TextBlob(text_str).sentiment.polarity
        if polarity > 0.05:
            return "Positive"
        elif polarity < -0.05:
            return "Negative"
        else:
            return "Neutral"
    except Exception:
        return "Neutral"

"""Observed university spellings: exact equivalence is applied; fuzzy matches need review."""

import re
from collections import Counter
from difflib import SequenceMatcher

from ..contracts import UniversityJudgment
from ..model import LocalModel, ModelError
from .normalizers import blank, text


def build_university_map(values, *, judge=False, model=None):
    """Cross-file exact formatting map plus review-only equivalence proposals.

    Caller must enforce PreparedData before enabling model assistance.
    No hard-coded institution database or fuzzy/transitive auto-merging.
    """
    observed = [
        surface_normalize(value) for value in values if isinstance(value, str) and not blank(value)
    ]
    counts = Counter(observed)
    groups = {}
    for value in sorted(counts):
        groups.setdefault(value.casefold(), []).append(value)
    mapping = {}
    for variants in groups.values():
        canonical = choose_canonical_variant(variants, counts)
        for value in variants:
            mapping[value] = canonical
    unique = sorted(set(mapping.values()))
    proposals = []
    limited = len(unique) > 100
    examined = 0
    client = (model or LocalModel()) if judge else None
    for i, a in enumerate(unique[:100]):
        for b in unique[i + 1 : 100]:
            similarity = string_similarity(a, b)
            if not judge and similarity < 0.75:
                continue
            if examined >= 200:
                limited = True
                break
            examined += 1
            proposal = {"value_a": a, "value_b": b, "similarity": similarity, "applied": False}
            if judge:
                decision = client.analyze(
                    "structured",
                    {"task": "university_equivalence", "value_a": a, "value_b": b},
                    UniversityJudgment,
                )
                decision = UniversityJudgment.model_validate(decision.model_dump())
                if decision.value_a != a or decision.value_b != b:
                    raise ModelError("University judgment changed its source values")
                proposal.update(decision.model_dump())
                if decision.same_university is False and decision.confidence >= 0.95:
                    continue
            proposals.append(proposal)
        if examined >= 200:
            break
    return mapping, proposals, limited


def surface_normalize(value):
    """
    First-pass formatting only.
    No university names are hard-coded.
    """
    if blank(value):
        return value

    s = text(value)
    s = re.sub(r"\s+", " ", s).strip()

    # Preserve Arabic words; normalize whitespace only.
    if re.search(r"[\u0600-\u06FF]", s):
        return s

    small_words = {"of", "and", "the", "for", "in", "at"}
    words = s.split()
    formatted = []

    for index, word in enumerate(words):
        low = word.casefold()

        if word.isupper() and 2 <= len(word) <= 6:
            formatted.append(word)
        elif index > 0 and low in small_words:
            formatted.append(low)
        else:
            formatted.append(word[:1].upper() + word[1:].lower())

    return " ".join(formatted)


def match_key(value):
    if blank(value):
        return ""

    s = str(value).casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[.,;:(){}\[\]_/\\\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^the\s+", "", s)
    return s


def token_sort_key(value):
    return " ".join(sorted(match_key(value).split()))


def string_similarity(a, b):
    a1 = match_key(a)
    b1 = match_key(b)

    if not a1 or not b1:
        return 0.0

    direct = SequenceMatcher(None, a1, b1).ratio()
    token_sorted = SequenceMatcher(
        None,
        token_sort_key(a),
        token_sort_key(b),
    ).ratio()

    return max(direct, token_sorted)


def choose_canonical_variant(values, global_counts):
    """
    Choose the canonical spelling from the actual observed data:
    1. most frequent
    2. shorter clean spelling
    3. alphabetical tie-break
    """
    candidates = list(dict.fromkeys(values))

    return sorted(
        candidates,
        key=lambda x: (
            -global_counts.get(x, 0),
            len(str(x)),
            str(x).casefold(),
        ),
    )[0]

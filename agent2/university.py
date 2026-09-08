import re
from collections import Counter
from difflib import SequenceMatcher

from .normalizers import blank, infer_supported_role, text


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
            formatted.append(
                word[:1].upper() + word[1:].lower()
            )

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


def qwen_same_university(a, b, qwen_pipe=None):
    """
    Optional hook for a local Qwen text-generation pipeline.
    If no pipeline is supplied, returns None.
    """
    if qwen_pipe is None:
        return None

    prompt = f"""
You are a data-standardization judge.

Decide whether these two values refer to the SAME university/institution.
Consider spelling variants, abbreviations, word order, translation,
Arabic/English naming, and minor typing differences.

Value A: {a}
Value B: {b}

Return exactly one word:
SAME
or
DIFFERENT
""".strip()

    try:
        result = qwen_pipe(
            prompt,
            max_new_tokens=5,
            do_sample=False,
        )

        if isinstance(result, list) and result:
            generated = result[0].get("generated_text", "")
        else:
            generated = str(result)

        answer = generated.strip().upper().split()[-1]

        if answer == "SAME":
            return True
        if answer == "DIFFERENT":
            return False

    except Exception:
        return None

    return None


def build_dynamic_university_map(
    structured_files,
    qwen_pipe=None,
):
    """
    Learn university equivalences from ALL files in the current run.

    Nothing here contains a hard-coded university name.
    """
    observed = []

    for _, df in structured_files.items():
        for column in df.columns:
            if infer_supported_role(column) != "university":
                continue

            for value in df[column].dropna():
                cleaned = surface_normalize(value)
                if not blank(cleaned):
                    observed.append(cleaned)

    counts = Counter(observed)
    unique_values = sorted(
        counts.keys(),
        key=lambda x: str(x).casefold(),
    )

    parent = {value: value for value in unique_values}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        root_a = find(a)
        root_b = find(b)

        if root_a != root_b:
            parent[root_b] = root_a

    for i in range(len(unique_values)):
        for j in range(i + 1, len(unique_values)):
            a = unique_values[i]
            b = unique_values[j]

            similarity = string_similarity(a, b)

            if similarity >= 0.93:
                union(a, b)
                continue

            if (
                0.75 <= similarity < 0.93
                and qwen_pipe is not None
            ):
                same = qwen_same_university(
                    a,
                    b,
                    qwen_pipe=qwen_pipe,
                )
                if same is True:
                    union(a, b)

    groups = {}

    for value in unique_values:
        groups.setdefault(find(value), []).append(value)

    mapping = {}

    for variants in groups.values():
        canonical = choose_canonical_variant(
            variants,
            counts,
        )

        for variant in variants:
            mapping[variant] = canonical

    return mapping


def apply_dynamic_university_map(
    structured_files,
    university_map,
):
    out_files = {}

    for file_name, df in structured_files.items():
        out = df.copy(deep=True)

        for column in out.columns:
            if infer_supported_role(column) != "university":
                continue

            out[column] = out[column].map(
                lambda value: (
                    value
                    if blank(value)
                    else university_map.get(
                        surface_normalize(value),
                        surface_normalize(value),
                    )
                )
            )

        out_files[file_name] = out

    return out_files

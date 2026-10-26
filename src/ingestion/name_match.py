import re
from difflib import SequenceMatcher

LEGAL_SUFFIXES = {"pty", "ltd", "limited", "cc", "inc", "incorporated", "sa", "sarl", "bv", "llc"}


def normalize_name(value: str | None) -> str:
    if value is None:
        return ""

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    tokens = [token for token in value.split() if token not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def token_overlap(a: str, b: str) -> float:
    a_tokens = set(normalize_name(a).split())
    b_tokens = set(normalize_name(b).split())

    if not a_tokens and not b_tokens:
        return 0.0
    if not a_tokens or not b_tokens:
        return 0.0

    union = a_tokens | b_tokens
    if not union:
        return 0.0

    return len(a_tokens & b_tokens) / len(union)


def name_similarity(a: str, b: str) -> float:
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)

    if not a_norm and not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0

    if a_norm in b_norm or b_norm in a_norm:
        return 0.92

    seq_score = SequenceMatcher(None, a_norm, b_norm).ratio()
    overlap = token_overlap(a_norm, b_norm)

    # weighted combination
    return max(seq_score, overlap) * 0.8 + min(seq_score, overlap) * 0.2


def classify_match(score: float) -> str:
    if score >= 0.95:
        return "exact"
    if score >= 0.80:
        return "strong_fuzzy"
    if score >= 0.60:
        return "needs_review"
    return "no_match"

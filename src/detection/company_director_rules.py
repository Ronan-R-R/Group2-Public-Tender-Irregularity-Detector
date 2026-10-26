from collections.abc import Iterable


def rule_r4_should_evaluate(enriched_suppliers: Iterable[object]) -> bool:
    # Example placeholder: evaluate only if at least one supplier has a confident match
    for supplier in enriched_suppliers:
        if getattr(supplier, "match_status", None) in {"exact", "strong_fuzzy"}:
            return True
    return False


def rule_r6_should_evaluate(enriched_suppliers: Iterable[object]) -> bool:
    for supplier in enriched_suppliers:
        if getattr(supplier, "matched_company_id", None) and getattr(
            supplier, "director_names", None
        ):
            return True
    return False

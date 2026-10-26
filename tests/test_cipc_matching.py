from ingestion.sample_registry import sample_company_registry
from ingestion.supplier_company_matcher import match_supplier_to_company


def test_exact_match() -> None:
    supplier = "Ndlovu Transport Services"
    company_names = ["Ndlovu Transport Services Pty Ltd"]
    result = match_supplier_to_company(supplier, company_names, source="sample")
    assert result.status in {"exact", "strong_fuzzy"}


def test_fuzzy_match() -> None:
    supplier = "Mokoena Construction"
    company_names = ["Mokoena Construction and Projects CC"]
    result = match_supplier_to_company(supplier, company_names, source="sample")
    assert result.confidence > 0.6


def test_ambiguous_match_is_not_auto_accepted() -> None:
    supplier = "Bophelo Civils"
    company_names = [
        "Bophelo Civils Limited",
        "Bophelo Civils Pty Ltd",
    ]
    result = match_supplier_to_company(supplier, company_names, source="sample")
    assert result.status == "needs_review"


def test_sample_registry_exists() -> None:
    companies = sample_company_registry()
    assert len(companies) > 0

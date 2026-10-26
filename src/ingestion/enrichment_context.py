from dataclasses import dataclass
from typing import Optional, List

@dataclass
class EnrichedSupplier:
    supplier_id: str
    supplier_name: str
    matched_company_id: Optional[str]
    matched_company_name: Optional[str]
    confidence: float
    source: str
    match_status: str
    director_names: List[str]

def build_enriched_supplier(
    supplier_id: str,
    supplier_name: str,
    matched_company_id: Optional[str],
    matched_company_name: Optional[str],
    confidence: float,
    source: str,
    match_status: str,
    director_names: Optional[List[str]] = None,
) -> EnrichedSupplier:
    return EnrichedSupplier(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        matched_company_id=matched_company_id,
        matched_company_name=matched_company_name,
        confidence=confidence,
        source=source,
        match_status=match_status,
        director_names=director_names or [],
    )
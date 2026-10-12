"""Factories for synthetic awards.

Field shapes mirror eTenders OCDS records; every name and ID is fictional.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from detection.context import InMemoryContext
from detection.models import Company, Tender

TenderFactory = Callable[..., Tender]
CompanyFactory = Callable[..., Company]

CLOSE = date(2025, 3, 14)


@pytest.fixture
def make_tender() -> TenderFactory:
    def factory(**overrides: Any) -> Tender:
        fields: dict[str, Any] = {
            "tender_id": "ocds-9t57fa-100001/award-1",
            "ocid": "ocds-9t57fa-100001",
            "title": "Supply and delivery of laboratory consumables for 36 months",
            "buyer_id": "dept-001",
            "buyer_name": "Fictional Provincial Department of Health",
            "supplier_id": "sup-001",
            "category": "Supplies: Medical",
            "procurement_method": "Request for Bid(Open-Tender)",
            "close_date": CLOSE,
            "award_value": Decimal("1287450.36"),
        }
        fields.update(overrides)
        return Tender(**fields)

    return factory


@pytest.fixture
def make_company() -> CompanyFactory:
    def factory(**overrides: Any) -> Company:
        fields: dict[str, Any] = {
            "company_id": "sup-001",
            "name": "Fictional Medical Supplies (Pty) Ltd",
            "registration_number": "2019/123456/07",
            "registration_date": date(2019, 6, 3),
            "status": "In Business",
            "industry": "Human health activities",
            "annual_return_dates": (date(2023, 6, 30), date(2024, 6, 28)),
        }
        fields.update(overrides)
        return Company(**fields)

    return factory


@pytest.fixture
def empty_ctx() -> InMemoryContext:
    return InMemoryContext(awards=())

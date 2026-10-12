"""Loader tests built on record shapes copied from the eTenders OCDS feed.

Company and person names are fictional; field structure is real.
"""

import gzip
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ingestion.ocds import LoadReport, awards_from_release, display_name, load_ocds, name_key


def release(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ocid": "ocds-9t57fa-90366",
        "buyer": {"id": "213", "name": "Gauteng - Infrastructure Development"},
        "tender": {
            "title": "Construction of a fictional clinic",
            "category": "Construction",
            "procurementMethodDetails": "Request for Bid(Open-Tender)",
            "tenderPeriod": {
                "startDate": "2024-08-30T00:00:00Z",
                "endDate": "2024-09-20T11:00:00Z",
            },
            "tenderers": [{"id": "22784", "name": "MAAA0000001 - (SOMEONE ELSE)"}],
            "contactPerson": {"name": "A. Official", "email": "official@example.gov.za"},
        },
        "awards": [
            {
                "id": "67218",
                "status": "active",
                "value": {"amount": 1287450.36, "currency": "ZAR"},
                "suppliers": [{"id": "540287", "name": "FICTIONAL BUILDERS"}],
            }
        ],
    }
    record.update(overrides)
    return record


def load_one(record: dict[str, Any]) -> tuple[list[Any], LoadReport]:
    report = LoadReport()
    return list(awards_from_release(record, report)), report


def test_maps_a_standard_award() -> None:
    (award,), report = load_one(release())
    t = award.tender

    assert t.tender_id == "ocds-9t57fa-90366/67218"
    assert t.buyer_id == "etenders:213"
    assert t.supplier_id == "etenders:540287"
    assert t.close_date == date(2024, 9, 20)
    assert t.award_value == Decimal("1287450.36")
    assert t.category == "Construction"
    assert award.company.name == "FICTIONAL BUILDERS"
    assert report.awards == 1


def test_tenderer_list_is_not_treated_as_bid_list() -> None:
    (award,), _ = load_one(release())

    assert award.tender.tenderer_ids is None


def test_never_reads_official_contact_details() -> None:
    (award,), _ = load_one(release())

    assert "official" not in repr(award).lower()


def test_supplier_id_zero_is_keyed_by_normalised_name() -> None:
    a = release(awards=[{"id": "1", "suppliers": [{"id": "0", "name": " (Fictional Builders)"}]}])
    b = release(
        ocid="ocds-9t57fa-2",
        awards=[{"id": "2", "suppliers": [{"id": "0", "name": "FICTIONAL  BUILDERS"}]}],
    )
    c = release(
        ocid="ocds-9t57fa-3",
        awards=[{"id": "3", "suppliers": [{"id": "0", "name": "Other Trading"}]}],
    )

    keys = [load_one(r)[0][0].tender.supplier_id for r in (a, b, c)]

    assert keys[0] == keys[1] == "name:FICTIONAL BUILDERS"
    assert keys[2] == "name:OTHER TRADING"


@pytest.mark.parametrize("amount", [0, 0.0, None, "abc", -5, True])
def test_unusable_amounts_become_missing(amount: object) -> None:
    record = release()
    record["awards"][0]["value"]["amount"] = amount

    (award,), _ = load_one(record)

    assert award.tender.award_value is None


@pytest.mark.parametrize("end", ["0001-01-01T00:00:00", "not a date", "", None, "1999-12-31"])
def test_unusable_close_dates_become_missing(end: object) -> None:
    record = release()
    record["tender"]["tenderPeriod"]["endDate"] = end

    (award,), _ = load_one(record)

    assert award.tender.close_date is None


def test_falls_back_to_main_procurement_category() -> None:
    record = release()
    record["tender"]["category"] = None
    record["tender"]["mainProcurementCategory"] = "works"

    (award,), _ = load_one(record)

    assert award.tender.category == "works"


def test_panel_award_yields_one_tender_per_award() -> None:
    record = release(
        awards=[
            {"id": "1", "suppliers": [{"id": "11", "name": "A"}]},
            {"id": "2", "suppliers": [{"id": "12", "name": "B"}]},
        ]
    )

    awards, _ = load_one(record)

    assert [a.tender.tender_id for a in awards] == [
        "ocds-9t57fa-90366/1",
        "ocds-9t57fa-90366/2",
    ]
    assert len({a.tender.ocid for a in awards}) == 1


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"buyer": {}}, "missing ocid or buyer"),
        ({"buyer": {"id": "0"}}, "missing ocid or buyer"),
        ({"ocid": ""}, "missing ocid or buyer"),
        ({"awards": [{"id": "1", "suppliers": []}]}, "no identifiable supplier"),
        (
            {"awards": [{"id": "1", "suppliers": [{"id": "0", "name": "  "}]}]},
            "no identifiable supplier",
        ),
    ],
)
def test_skips_unresolvable_awards_with_reason(overrides: dict[str, Any], reason: str) -> None:
    awards, report = load_one(release(**overrides))

    assert awards == []
    assert report.skipped[reason] == 1


def test_releases_without_awards_yield_nothing() -> None:
    awards, report = load_one(release(awards=[]))

    assert awards == []
    assert not report.skipped


@pytest.mark.parametrize(
    ("raw", "shown", "key"),
    [
        (
            "MAAA0213643 - (BRILLIANT TELECOMMUNICATIONS)",
            "BRILLIANT TELECOMMUNICATIONS",
            "BRILLIANT TELECOMMUNICATIONS",
        ),
        (" (KAYWEB)", "KAYWEB", "KAYWEB"),
        ("Nexia SAB&T", "Nexia SAB&T", "NEXIA SAB T"),
        (
            "  Fictional   Trading (Pty) Ltd ",
            "Fictional Trading (Pty) Ltd",
            "FICTIONAL TRADING PTY LTD",
        ),
    ],
)
def test_name_cleaning(raw: str, shown: str, key: str) -> None:
    assert display_name(raw) == shown
    assert name_key(raw) == key


def test_load_ocds_reads_gzip_and_counts_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl.gz"
    lines = [json.dumps(release()), "{not json", "[1, 2]", "", json.dumps(release(ocid="ocds-x-2"))]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    loaded, report = load_ocds(path)

    assert len(loaded) == 2
    assert report.records == 4
    assert report.skipped["unparseable line"] == 1
    assert report.skipped["line is not a JSON object"] == 1


def test_load_ocds_reads_plain_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text(json.dumps(release()) + "\n", encoding="utf-8")

    loaded, _ = load_ocds(path)

    assert len(loaded) == 1

"""Database writer tests against a real PostgreSQL 17.

Same rules as test_schema.py: TEST_DATABASE_URL must name a database ending in
"_test", and REQUIRE_DB=1 turns a missing database into a failure.
"""

import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from db import writer
from detection.anomaly import AnomalySignal
from detection.context import InMemoryContext
from detection.engine import evaluate_award
from detection.export import ScoredAward
from detection.models import Company, RuleResult, Severity, Tender
from detection.scorer import score

SOURCE = "https://example.test/ocds"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A database with no tender schema; each test starts from nothing."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail("REQUIRE_DB=1 but TEST_DATABASE_URL is not set")
        pytest.skip("TEST_DATABASE_URL not set")
    with writer.connect(url) as c:
        name = c.info.dbname
        if not name.endswith("_test"):
            pytest.fail(f"refusing to drop schema in database {name!r}: name must end in _test")
        c.execute("DROP SCHEMA IF EXISTS tender CASCADE")
        c.commit()
        yield c


def tender(n: int, ocid: str = "", **overrides: object) -> Tender:
    ocid = ocid or f"ocds-9t57fa-{n}"
    fields: dict[str, object] = {
        "tender_id": f"{ocid}/award-{n}",
        "ocid": ocid,
        "title": f"Fictional tender {n}",
        "buyer_id": "etenders:1",
        "buyer_name": "Fictional Department of Health",
        "supplier_id": f"etenders:{100 + n}",
        "category": "Supplies: Medical",
        "procurement_method": "Request for Bid(Open-Tender)",
        "close_date": date(2025, 3, 14),
        "award_date": date(2025, 4, 1),
        "award_value": Decimal("1287450.36"),
    }
    fields.update(overrides)
    return Tender(**fields)  # type: ignore[arg-type]


def company(t: Tender, name: str = "") -> Company:
    return Company(company_id=t.supplier_id, name=name or f"Fictional Supplier {t.supplier_id}")


def scored_by_engine(tenders: list[Tender]) -> list[ScoredAward]:
    """Score through the real engine, so every rule's output shape is written."""
    ctx = InMemoryContext(tenders)
    return [ScoredAward(t, company(t), evaluate_award(t, company(t), (), ctx)) for t in tenders]


def count(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) FROM tender.{table}").fetchone()  # noqa: S608
    assert row is not None
    return int(row[0])


def test_ensure_schema_applies_once(conn: psycopg.Connection) -> None:
    assert writer.ensure_schema(conn) is True
    assert writer.ensure_schema(conn) is False
    assert count(conn, "scoring_runs") == 0


def test_write_run_stores_records_scores_and_every_rule_result(
    conn: psycopg.Connection,
) -> None:
    writer.ensure_schema(conn)
    # Two awards in one contracting process share one tenders row.
    tenders = [tender(1), tender(2, ocid="ocds-9t57fa-1"), tender(3)]
    scored = scored_by_engine(tenders)

    report = writer.write_run(conn, scored, SOURCE)

    assert (report.awards, report.rule_results, report.runs_pruned) == (3, 36, 0)
    assert count(conn, "buyers") == 1
    assert count(conn, "tenders") == 2
    assert count(conn, "companies") == 3
    assert count(conn, "awards") == 3
    assert count(conn, "risk_scores") == 3
    assert count(conn, "rule_results") == 36
    row = conn.execute(
        "SELECT source, awards_scored FROM tender.scoring_runs WHERE run_id = %s",
        (report.run_id,),
    ).fetchone()
    assert row == (SOURCE, 3)


def test_private_evidence_and_anomaly_are_stored(conn: psycopg.Connection) -> None:
    writer.ensure_schema(conn)
    t = tender(1)
    pep = RuleResult.fire(
        "R6",
        "Director matches a politically exposed persons list",
        Severity.CRITICAL,
        {"directors_checked": 1, "matched_directors": 1},
        private_evidence={"matches": [{"director_name": "A. Fictional Person"}]},
        needs_review=True,
    )
    signal = AnomalySignal(t.tender_id, 98.76, 1.0, 1.0, 0.1, 0.1)

    writer.write_run(conn, [ScoredAward(t, company(t), score([pep]), signal)], SOURCE)

    row = conn.execute(
        "SELECT rs.needs_review, rs.anomaly_percentile, rr.points, "
        "rr.private_evidence -> 'matches' -> 0 ->> 'director_name' "
        "FROM tender.risk_scores rs JOIN tender.rule_results rr USING (run_id, award_id)"
    ).fetchone()
    assert row == (True, Decimal("98.8"), 25, "A. Fictional Person")


def test_rerun_upserts_and_keeps_cipc_enrichment(conn: psycopg.Connection) -> None:
    writer.ensure_schema(conn)
    t = tender(1)
    writer.write_run(conn, scored_by_engine([t]), SOURCE)
    conn.execute(
        "UPDATE tender.companies SET registration_number = '2019/123456/07' WHERE company_id = %s",
        (t.supplier_id,),
    )
    conn.commit()

    renamed = ScoredAward(t, company(t, "Fictional Supplier Renamed"), score([]))
    writer.write_run(conn, [renamed], SOURCE)

    assert count(conn, "awards") == 1
    assert count(conn, "scoring_runs") == 2
    row = conn.execute(
        "SELECT name, registration_number FROM tender.companies WHERE company_id = %s",
        (t.supplier_id,),
    ).fetchone()
    assert row == ("Fictional Supplier Renamed", "2019/123456/07")


def test_only_the_latest_runs_are_kept(conn: psycopg.Connection) -> None:
    writer.ensure_schema(conn)
    scored = scored_by_engine([tender(1)])

    reports = [writer.write_run(conn, scored, SOURCE) for _ in range(writer.KEEP_RUNS + 2)]

    assert [r.runs_pruned for r in reports] == [0] * writer.KEEP_RUNS + [1, 1]
    rows = conn.execute("SELECT run_id FROM tender.scoring_runs ORDER BY run_id").fetchall()
    assert [r[0] for r in rows] == [r.run_id for r in reports[-writer.KEEP_RUNS :]]
    assert count(conn, "rule_results") == 12 * writer.KEEP_RUNS


def test_directors_past_retention_are_purged_on_write(conn: psycopg.Connection) -> None:
    writer.ensure_schema(conn)
    old = tender(1, award_date=date(2020, 1, 10), close_date=date(2019, 12, 1))
    recent = tender(2, award_date=date.today())
    writer.write_run(conn, scored_by_engine([old, recent]), SOURCE)
    conn.execute(
        "INSERT INTO tender.directors (director_id, full_name) "
        "VALUES ('d-old', 'A. Fictional Person'), ('d-new', 'B. Fictional Person')"
    )
    conn.execute(
        "INSERT INTO tender.company_directors (company_id, director_id) "
        "VALUES (%s, 'd-old'), (%s, 'd-new')",
        (old.supplier_id, recent.supplier_id),
    )
    conn.commit()

    report = writer.write_run(conn, scored_by_engine([old, recent]), SOURCE)

    assert report.directors_purged == 1
    rows = conn.execute("SELECT director_id FROM tender.directors").fetchall()
    assert rows == [("d-new",)]


def test_a_failed_write_commits_nothing(conn: psycopg.Connection) -> None:
    writer.ensure_schema(conn)
    good = scored_by_engine([tender(1)])
    writer.write_run(conn, good, SOURCE)
    # Values beyond numeric(20, 2) are rejected by the database mid-write.
    too_big = tender(2, award_value=Decimal("1e19"))
    bad = [*good, ScoredAward(too_big, company(too_big), score([]))]

    with pytest.raises(psycopg.errors.NumericValueOutOfRange):
        writer.write_run(conn, bad, SOURCE)

    assert count(conn, "scoring_runs") == 1
    assert count(conn, "awards") == 1
    assert count(conn, "companies") == 1

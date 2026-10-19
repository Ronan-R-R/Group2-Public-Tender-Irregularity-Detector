"""Schema tests against a real PostgreSQL 17.

They run in CI against a Postgres service container. Locally they need
TEST_DATABASE_URL pointing at a database whose name ends in "_test": the
fixture drops and recreates the "tender" schema, so it refuses anything else.
Without TEST_DATABASE_URL they skip, unless REQUIRE_DB=1 (set in CI), in which
case a missing database is a failure.
"""

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

SCHEMA = Path(__file__).resolve().parents[2] / "src" / "db" / "schema.sql"


@pytest.fixture(scope="module")
def db() -> Iterator[psycopg.Connection]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail("REQUIRE_DB=1 but TEST_DATABASE_URL is not set")
        pytest.skip("TEST_DATABASE_URL not set")
    with psycopg.connect(url, autocommit=True) as conn:
        name = conn.info.dbname
        if not name.endswith("_test"):
            pytest.fail(f"refusing to drop schema in database {name!r}: name must end in _test")
        conn.execute("DROP SCHEMA IF EXISTS tender CASCADE")
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.autocommit = False
        yield conn


@pytest.fixture
def cur(db: psycopg.Connection) -> Iterator[psycopg.Cursor]:
    """Each test runs in a transaction that is rolled back afterwards."""
    with db.cursor() as c:
        c.execute("SET search_path = tender")
        yield c
    db.rollback()


def seed(cur: psycopg.Cursor) -> None:
    cur.execute("INSERT INTO buyers VALUES ('etenders:1', 'Fictional Department of Health')")
    cur.execute(
        "INSERT INTO tenders (ocid, buyer_id, title, category, close_date) "
        "VALUES ('ocds-9t57fa-1', 'etenders:1', 'Lab consumables', "
        "'Supplies: Medical', '2025-03-14')"
    )
    cur.execute(
        "INSERT INTO companies (company_id, name) VALUES ('etenders:100', 'Fictional Supplies')"
    )
    cur.execute(
        "INSERT INTO awards (award_id, ocid, supplier_id, value) "
        "VALUES ('ocds-9t57fa-1/1', 'ocds-9t57fa-1', 'etenders:100', 1287450.36)"
    )


def violates(cur: psycopg.Cursor, statement: str) -> type[Exception]:
    """Run a statement expected to fail; return the error type and reset state."""
    cur.execute("SAVEPOINT expect_error")
    with pytest.raises(psycopg.errors.IntegrityError) as err:
        cur.execute(statement)
    cur.execute("ROLLBACK TO SAVEPOINT expect_error")
    return type(err.value)


def test_schema_creates_every_table(cur: psycopg.Cursor) -> None:
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'tender' ORDER BY 1")

    assert [r[0] for r in cur.fetchall()] == [
        "awards", "buyers", "companies", "company_annual_returns", "company_directors",
        "directors", "pep_matches", "risk_scores", "rule_results", "scoring_runs",
        "tender_bidders", "tenders",
    ]  # fmt: skip


def test_nothing_is_in_the_public_schema(cur: psycopg.Cursor) -> None:
    cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")

    row = cur.fetchone()
    assert row is not None and row[0] == 0


def test_row_level_security_is_on_for_every_table(cur: psycopg.Cursor) -> None:
    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'tender' AND c.relkind = 'r' AND NOT c.relrowsecurity"
    )

    assert cur.fetchall() == []


def test_valid_records_insert(cur: psycopg.Cursor) -> None:
    seed(cur)
    cur.execute("SELECT value FROM awards WHERE award_id = 'ocds-9t57fa-1/1'")

    row = cur.fetchone()
    assert row is not None and str(row[0]) == "1287450.36"


@pytest.mark.parametrize(
    ("statement", "error"),
    [
        (
            "INSERT INTO awards (award_id, ocid, supplier_id, value) "
            "VALUES ('ocds-9t57fa-1/2', 'ocds-9t57fa-1', 'etenders:100', 0)",
            psycopg.errors.CheckViolation,
        ),
        (
            "INSERT INTO awards (award_id, ocid, supplier_id, currency) "
            "VALUES ('ocds-9t57fa-1/2', 'ocds-9t57fa-1', 'etenders:100', 'zar')",
            psycopg.errors.CheckViolation,
        ),
        (
            "INSERT INTO awards (award_id, ocid, supplier_id) "
            "VALUES ('other/2', 'ocds-9t57fa-1', 'etenders:100')",
            psycopg.errors.CheckViolation,
        ),
        (
            "INSERT INTO awards (award_id, ocid, supplier_id) "
            "VALUES ('ocds-9t57fa-1/2', 'ocds-9t57fa-1', 'etenders:999')",
            psycopg.errors.ForeignKeyViolation,
        ),
        (
            "INSERT INTO tenders (ocid, buyer_id, close_date) "
            "VALUES ('ocds-9t57fa-2', 'etenders:1', '0001-01-01')",
            psycopg.errors.CheckViolation,
        ),
        (
            "INSERT INTO tenders (ocid, buyer_id) VALUES ('not-an-ocid', 'etenders:1')",
            psycopg.errors.CheckViolation,
        ),
    ],
)
def test_procurement_constraints(
    cur: psycopg.Cursor, statement: str, error: type[Exception]
) -> None:
    seed(cur)

    assert issubclass(violates(cur, statement), error)


def test_director_appointment_dates_must_be_ordered(cur: psycopg.Cursor) -> None:
    seed(cur)
    cur.execute("INSERT INTO directors (director_id, full_name) VALUES ('dir-1', 'A. Person')")

    error = violates(
        cur,
        "INSERT INTO company_directors "
        "VALUES ('etenders:100', 'dir-1', '2024-05-01', '2024-04-01')",
    )

    assert issubclass(error, psycopg.errors.CheckViolation)


def scored(cur: psycopg.Cursor, score: int, level: str) -> int:
    seed(cur)
    cur.execute("INSERT INTO scoring_runs (source) VALUES ('test') RETURNING run_id")
    row = cur.fetchone()
    assert row is not None
    run_id = int(row[0])
    cur.execute(
        "INSERT INTO risk_scores (run_id, award_id, score, uncapped_score, level, coverage) "
        "VALUES (%s, 'ocds-9t57fa-1/1', %s, %s, %s, 0.5)",
        (run_id, score, score, level),
    )
    return run_id


@pytest.mark.parametrize(
    ("score", "level"), [(49, "flag"), (50, "none"), (75, "flag"), (101, "alert")]
)
def test_score_and_level_must_agree(cur: psycopg.Cursor, score: int, level: str) -> None:
    cur.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.CheckViolation):
        scored(cur, score, level)
    cur.execute("ROLLBACK TO SAVEPOINT s")


@pytest.mark.parametrize(
    ("score", "level"), [(0, "none"), (50, "flag"), (75, "alert"), (100, "alert")]
)
def test_valid_scores_insert(cur: psycopg.Cursor, score: int, level: str) -> None:
    scored(cur, score, level)


@pytest.mark.parametrize(
    ("fired", "evaluated", "severity", "points"),
    [(True, False, "high", 15), (True, True, "high", 8), (False, True, "low", 3)],
)
def test_rule_result_invariants(
    cur: psycopg.Cursor, fired: bool, evaluated: bool, severity: str, points: int
) -> None:
    run_id = scored(cur, 0, "none")

    error = violates(
        cur,
        sql.SQL(
            "INSERT INTO rule_results "
            "(run_id, award_id, rule_id, severity, fired, evaluated, points) "
            "VALUES ({}, 'ocds-9t57fa-1/1', 'R10', {}, {}, {}, {})"
        )
        .format(
            sql.Literal(run_id), sql.Literal(severity), sql.Literal(fired),
            sql.Literal(evaluated), sql.Literal(points),
        )
        .as_string(cur.connection),
    )  # fmt: skip

    assert issubclass(error, psycopg.errors.CheckViolation)


def test_deleting_a_tender_cascades_to_awards_and_scores(cur: psycopg.Cursor) -> None:
    run_id = scored(cur, 15, "none")
    cur.execute(
        "INSERT INTO rule_results (run_id, award_id, rule_id, severity, fired, evaluated, points) "
        "VALUES (%s, 'ocds-9t57fa-1/1', 'R10', 'high', true, true, 15)",
        (run_id,),
    )

    cur.execute("DELETE FROM tenders WHERE ocid = 'ocds-9t57fa-1'")

    for table in ("awards", "risk_scores", "rule_results"):
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        row = cur.fetchone()
        assert row is not None and row[0] == 0, table


def test_a_company_with_awards_cannot_be_deleted(cur: psycopg.Cursor) -> None:
    seed(cur)

    error = violates(cur, "DELETE FROM companies WHERE company_id = 'etenders:100'")

    assert issubclass(error, psycopg.errors.ForeignKeyViolation)


def director(cur: psycopg.Cursor, director_id: str, company_id: str) -> None:
    cur.execute(
        "INSERT INTO directors (director_id, full_name) VALUES (%s, 'A. Person')", (director_id,)
    )
    cur.execute(
        "INSERT INTO company_directors (company_id, director_id) VALUES (%s, %s)",
        (company_id, director_id),
    )


def test_retention_deletes_directors_whose_last_link_has_expired(cur: psycopg.Cursor) -> None:
    seed(cur)  # award closed 2025-03-14
    cur.execute(
        "INSERT INTO companies (company_id, name) VALUES ('etenders:200', 'No Awards Trading')"
    )
    director(cur, "recent", "etenders:100")
    director(cur, "unlinked", "etenders:200")
    cur.execute(
        "INSERT INTO pep_matches (director_id, source, source_ref, match_score) "
        "VALUES ('unlinked', 'test', 'x', 0.9)"
    )

    cur.execute("SELECT purge_expired_directors(as_of => %s)", (date(2026, 3, 1),))
    row = cur.fetchone()

    assert row is not None and row[0] == 1
    cur.execute("SELECT director_id FROM directors")
    assert [r[0] for r in cur.fetchall()] == ["recent"]
    cur.execute("SELECT count(*) FROM pep_matches")
    pep = cur.fetchone()
    assert pep is not None and pep[0] == 0


def test_retention_expires_a_director_twelve_months_after_the_last_award(
    cur: psycopg.Cursor,
) -> None:
    seed(cur)
    director(cur, "d", "etenders:100")

    cur.execute("SELECT purge_expired_directors(as_of => %s)", (date(2026, 3, 14),))
    kept = cur.fetchone()
    cur.execute("SELECT purge_expired_directors(as_of => %s)", (date(2026, 3, 15),))
    removed = cur.fetchone()

    assert kept is not None and kept[0] == 0
    assert removed is not None and removed[0] == 1


def test_retention_treats_an_undated_award_as_recent(cur: psycopg.Cursor) -> None:
    seed(cur)
    cur.execute("UPDATE tenders SET close_date = NULL")
    director(cur, "d", "etenders:100")

    cur.execute("SELECT purge_expired_directors()")
    row = cur.fetchone()

    assert row is not None and row[0] == 0

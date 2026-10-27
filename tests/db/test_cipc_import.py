"""CIPC import and schema migrations against a real PostgreSQL 17.

Same rules as test_schema.py: TEST_DATABASE_URL must name a database ending in
"_test", and REQUIRE_DB=1 turns a missing database into a failure. Every name
and number is invented.
"""

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
import pytest

from db import writer
from db.cipc_import import import_cipc
from ingestion.cipc_csv import COMPANY_COLUMNS, DIRECTOR_COLUMNS, CipcData, load_cipc

COMPANY = (
    "etenders:900001,FICTIONAL SUPPLIES (PTY) LTD,2019/123456/07,2019-06-03,In Business,"
    "Human health activities,2020-06-30;2021-06-29,2026-10-27"
)
DIRECTOR = "etenders:900001,dir-0001,A. Fictional Person,2019-06-03,,1980-01-01"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail("REQUIRE_DB=1 but TEST_DATABASE_URL is not set")
        pytest.skip("TEST_DATABASE_URL not set")
    with writer.connect(url) as c:
        if not c.info.dbname.endswith("_test"):
            pytest.fail("refusing to drop schema: database name must end in _test")
        c.execute("DROP SCHEMA IF EXISTS tender CASCADE")
        writer.ensure_schema(c)
        yield c


def cipc(tmp_path: Path, companies: list[str], directors: list[str]) -> CipcData:
    (tmp_path / "companies.csv").write_text(
        "\n".join([",".join(COMPANY_COLUMNS), *companies]) + "\n", encoding="utf-8"
    )
    (tmp_path / "directors.csv").write_text(
        "\n".join([",".join(DIRECTOR_COLUMNS), *directors]) + "\n", encoding="utf-8"
    )
    return load_cipc(tmp_path)


def one(conn: psycopg.Connection, query: str) -> tuple[object, ...]:
    row = conn.execute(query).fetchone()
    assert row is not None
    return tuple(row)


def test_a_new_database_records_every_migration(conn: psycopg.Connection) -> None:
    versions = [r[0] for r in conn.execute("SELECT version FROM tender.schema_migrations")]

    assert versions == sorted(p.stem for p in writer.MIGRATIONS_DIR.glob("*.sql"))
    assert writer.migrate(conn) == []


def test_a_database_from_before_migrations_is_brought_up_to_date(
    conn: psycopg.Connection,
) -> None:
    # The production database was created before birth_date and the tracking table.
    conn.execute("ALTER TABLE tender.directors DROP COLUMN birth_date")
    conn.execute("DROP TABLE tender.schema_migrations")

    applied = writer.migrate(conn)

    assert applied == ["0001_director_birth_date"]
    assert one(conn, "SELECT count(*) FROM information_schema.columns "
               "WHERE table_schema = 'tender' AND table_name = 'directors' "
               "AND column_name = 'birth_date'") == (1,)  # fmt: skip
    assert one(conn, "SELECT relrowsecurity FROM pg_class "
               "WHERE oid = 'tender.schema_migrations'::regclass") == (True,)  # fmt: skip
    assert writer.migrate(conn) == []


def test_import_writes_companies_returns_directors_and_links(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    report = import_cipc(conn, cipc(tmp_path, [COMPANY], [DIRECTOR]))

    assert (report.companies, report.directors, report.links, report.annual_returns) == (1, 1, 1, 2)
    assert one(
        conn,
        "SELECT name, registration_number, registration_date, status, industry, "
        "cipc_match_confidence FROM tender.companies",
    ) == (
        "FICTIONAL SUPPLIES (PTY) LTD",
        "2019/123456/07",
        date(2019, 6, 3),
        "In Business",
        "Human health activities",
        1,
    )
    assert one(conn, "SELECT full_name, birth_date FROM tender.directors") == (
        "A. Fictional Person",
        date(1980, 1, 1),
    )
    assert one(conn, "SELECT count(*) FROM tender.company_annual_returns") == (2,)


def test_import_keeps_the_etenders_name_of_an_existing_supplier(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    conn.execute(
        "INSERT INTO tender.companies (company_id, name) "
        "VALUES ('etenders:900001', 'Fictional Supplies')"
    )

    import_cipc(conn, cipc(tmp_path, [COMPANY], []))

    assert one(conn, "SELECT name, registration_number FROM tender.companies") == (
        "Fictional Supplies",
        "2019/123456/07",
    )


def test_reimport_replaces_links_and_returns_for_listed_companies(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    import_cipc(conn, cipc(tmp_path / "a", [COMPANY], [DIRECTOR]))
    replaced = DIRECTOR.replace("dir-0001", "dir-0002").replace("A. Fictional", "B. Fictional")
    never_filed = COMPANY.replace("2020-06-30;2021-06-29", "none")

    import_cipc(conn, cipc(tmp_path / "b", [never_filed], [replaced]))

    links = conn.execute("SELECT director_id FROM tender.company_directors").fetchall()
    assert links == [("dir-0002",)]
    assert one(conn, "SELECT count(*) FROM tender.company_annual_returns") == (0,)


def test_unknown_annual_returns_leave_existing_ones_alone(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    import_cipc(conn, cipc(tmp_path / "a", [COMPANY], []))

    import_cipc(conn, cipc(tmp_path / "b", [COMPANY.replace("2020-06-30;2021-06-29", "")], []))

    assert one(conn, "SELECT count(*) FROM tender.company_annual_returns") == (2,)


def test_a_failed_import_writes_nothing(conn: psycopg.Connection, tmp_path: Path) -> None:
    # Another company in the database already holds this registration number.
    conn.execute(
        "INSERT INTO tender.companies (company_id, name, registration_number) "
        "VALUES ('etenders:900099', 'Other', '2019/123456/07')"
    )

    with pytest.raises(psycopg.errors.UniqueViolation):
        import_cipc(conn, cipc(tmp_path, [COMPANY], [DIRECTOR]))

    assert one(conn, "SELECT count(*) FROM tender.directors") == (0,)
    assert one(conn, "SELECT count(*) FROM tender.company_annual_returns") == (0,)
    assert one(conn, "SELECT count(*) FROM tender.companies") == (1,)

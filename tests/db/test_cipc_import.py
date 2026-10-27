"""CIPC import and schema migrations against a real PostgreSQL 17.

Same rules as test_schema.py: TEST_DATABASE_URL must name a database ending in
"_test", and REQUIRE_DB=1 turns a missing database into a failure. Every name
and number is invented.
"""

import importlib.util
import json
import os
import threading
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import ModuleType

import psycopg
import pytest

from db import writer
from db.cipc_import import import_cipc, read_cipc
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
    conn.execute("ALTER TABLE tender.companies DROP COLUMN annual_returns_checked")
    conn.execute("DROP TABLE tender.schema_migrations")

    applied = writer.migrate(conn)

    assert applied == ["0001_director_birth_date", "0002_annual_returns_checked"]
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


def test_two_migrators_at_once_apply_each_migration_once(conn: psycopg.Connection) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    conn.execute("ALTER TABLE tender.directors DROP COLUMN birth_date")
    conn.execute("DELETE FROM tender.schema_migrations")
    result: dict[str, object] = {}

    def second_migrator() -> None:
        with writer.connect(url) as c:
            try:
                result["applied"] = writer.migrate(c)
            except psycopg.Error as e:
                result["error"] = e

    with writer.connect(url) as first:
        # The first migrator is mid-migration: lock held, column added, not committed.
        first.execute("BEGIN")
        first.execute("SELECT pg_advisory_xact_lock(%s)", (writer._MIGRATION_LOCK,))
        first.execute(
            "ALTER TABLE tender.directors ADD COLUMN birth_date date "
            "CHECK (birth_date >= DATE '1900-01-01')"
        )
        first.execute(
            "INSERT INTO tender.schema_migrations (version) VALUES ('0001_director_birth_date')"
        )
        thread = threading.Thread(target=second_migrator)
        thread.start()
        _wait_until_blocked(conn, timeout=10)
        first.execute("COMMIT")
        thread.join(timeout=10)

    # 0001 was applied by the first migrator while the second waited; the
    # second re-checked under the lock, skipped it, and applied only 0002.
    assert result == {"applied": ["0002_annual_returns_checked"]}
    assert one(conn, "SELECT count(*) FROM tender.schema_migrations") == (2,)


def _wait_until_blocked(conn: psycopg.Connection, timeout: float) -> None:
    """Poll until another session is waiting on a lock, or fail."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = conn.execute("SELECT count(*) FROM pg_locks WHERE NOT granted").fetchone()
        if row is not None and row[0] > 0:
            return
        time.sleep(0.05)
    pytest.fail("the second migrator never waited for the lock")


def test_read_cipc_returns_what_was_imported(conn: psycopg.Connection, tmp_path: Path) -> None:
    unknown_returns = (
        COMPANY.replace("900001", "900002")
        .replace("123456", "654321")
        .replace("2020-06-30;2021-06-29", "")
    )
    never_filed = (
        COMPANY.replace("900001", "900003")
        .replace("123456", "111111")
        .replace("2020-06-30;2021-06-29", "none")
    )
    import_cipc(conn, cipc(tmp_path, [COMPANY, unknown_returns, never_filed], [DIRECTOR]))
    # A supplier the pipeline knows but nobody looked up on CIPC.
    conn.execute("INSERT INTO tender.companies (company_id, name) VALUES ('etenders:1', 'X')")

    data = read_cipc(conn)

    assert set(data.records) == {"etenders:900001", "etenders:900002", "etenders:900003"}
    returns = {cid: r.company.annual_return_dates for cid, r in data.records.items()}
    assert returns == {
        "etenders:900001": (date(2020, 6, 30), date(2021, 6, 29)),
        "etenders:900002": None,  # not looked up: R3 must not run
        "etenders:900003": (),  # looked up, never filed: R3 may fire
    }
    (director,) = data.directors["etenders:900001"]
    assert (director.director_id, director.birth_date) == ("dir-0001", date(1980, 1, 1))
    assert data.directors["etenders:900002"] == ()


def test_a_blank_reimport_keeps_known_annual_returns(
    conn: psycopg.Connection, tmp_path: Path
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    import_cipc(conn, cipc(tmp_path / "a", [COMPANY], []))
    import_cipc(conn, cipc(tmp_path / "b", [COMPANY.replace("2020-06-30;2021-06-29", "")], []))

    record = read_cipc(conn).records["etenders:900001"]

    assert record.company.annual_return_dates == (date(2020, 6, 30), date(2021, 6, 29))


def test_the_build_scores_with_cipc_data_from_the_database(
    conn: psycopg.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _script("build_dashboard_data")
    # Registered 22 days before the tender closed: R2 must fire.
    young = COMPANY.replace("2019-06-03", "2025-02-20").replace("2020-06-30;2021-06-29", "")
    director = DIRECTOR.replace("2019-06-03", "2025-02-20")
    import_cipc(conn, cipc(tmp_path, [young], [director]))
    feed = tmp_path / "feed.jsonl"
    feed.write_text(
        '{"ocid":"ocds-9t57fa-1","buyer":{"id":"1","name":"Fictional Dept"},'
        '"tender":{"title":"Fictional tender","tenderPeriod":{"endDate":"2025-03-14"}},'
        '"awards":[{"id":"1","suppliers":[{"id":"900001","name":"Fictional Supplies"}],'
        '"value":{"amount":1000,"currency":"ZAR"}}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    out = tmp_path / "out"

    code = build.main(["--ocds", str(feed), "--out", str(out), "--cipc-from-db", "--write-db"])

    assert code == 0
    published = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*.json"))
    shard = json.loads(next((out / "details").glob("*.json")).read_text(encoding="utf-8"))
    (detail,) = shard.values()
    rules = {r["rule_id"]: r for r in detail["breakdown"]}
    assert rules["R2"]["fired"] is True
    assert rules["R3"]["evaluated"] is False
    assert "A. Fictional Person" not in published
    assert "1980-01-01" not in published


def _script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

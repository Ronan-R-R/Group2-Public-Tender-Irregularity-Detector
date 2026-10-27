"""scripts/build_dashboard_data.py: log safety and what the published build contains."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import psycopg
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_dashboard_data.py"


@pytest.fixture(scope="module")
def build() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_dashboard_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_malformed_url_error_never_reveals_the_password(build: ModuleType) -> None:
    # An unencoded "%" in the password: libpq's own message quotes this token.
    url = "postgresql://postgres.ref:Fict10nal%Zz]@db.example.test:5432/postgres"
    with pytest.raises(psycopg.Error) as err:
        psycopg.connect(url, connect_timeout=1)
    assert "Fict10nal" in str(err.value)  # the leak this guards against is real

    described = build.describe_db_error(err.value, url)

    assert "Fict10nal" not in described
    assert "example.test" not in described
    assert described.startswith(type(err.value).__name__)


def test_main_reports_a_bad_url_without_the_password(
    build: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    feed = tmp_path / "feed.jsonl"
    feed.write_text(
        '{"ocid":"ocds-9t57fa-1","buyer":{"id":"1","name":"Fictional Dept"},'
        '"tender":{"title":"Fictional tender"},'
        '"awards":[{"id":"1","suppliers":[{"id":"100","name":"Fictional Supplier"}],'
        '"value":{"amount":1000,"currency":"ZAR"}}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:Fict10nal%Zz]@db.example.test/postgres")

    code = build.main(["--ocds", str(feed), "--out", str(tmp_path / "out"), "--write-db"])

    assert code == 3
    assert "database write failed" in caplog.text
    assert "Fict10nal" not in caplog.text


def test_a_connection_failure_names_the_host_but_not_the_password(build: ModuleType) -> None:
    url = "postgresql://postgres.ref:Fict10nalPassw0rd@db.example.test:5432/postgres"
    with pytest.raises(psycopg.OperationalError) as err:
        psycopg.connect(url, connect_timeout=1)
    # libpq does not normally echo the password here; prove the strip works anyway.
    err.value.args = (f"{err.value} (sent Fict10nalPassw0rd)",)
    assert "Fict10nalPassw0rd" in str(err.value)

    described = build.describe_db_error(err.value, url)

    assert "db.example.test" in described
    assert "Fict10nalPassw0rd" not in described


def feed_with_sample_lookalike(tmp_path: Path) -> Path:
    # A real-looking supplier whose name shares "Construction and Projects"
    # with an invented sample company, the case that leaked onto the live site.
    feed = tmp_path / "feed.jsonl"
    feed.write_text(
        '{"ocid":"ocds-9t57fa-1","buyer":{"id":"1","name":"Fictional Dept"},'
        '"tender":{"title":"Fictional tender"},'
        '"awards":[{"id":"1","suppliers":[{"id":"100",'
        '"name":"Fictional Mokoena Construction and Projects"}],'
        '"value":{"amount":1000,"currency":"ZAR"}}]}\n',
        encoding="utf-8",
    )
    return feed


def published_details(out: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for shard in sorted((out / "details").glob("*.json")):
        rows.extend(json.loads(shard.read_text(encoding="utf-8")).values())
    return rows


def test_the_published_build_never_contains_sample_registry_matches(
    build: ModuleType, tmp_path: Path
) -> None:
    out = tmp_path / "out"

    code = build.main(["--ocds", str(feed_with_sample_lookalike(tmp_path)), "--out", str(out)])

    assert code == 0
    details = published_details(out)
    assert details
    assert all(d.get("supplier_match") is None for d in details)
    assert "Mokoena Construction and Projects CC" not in "".join(
        p.read_text(encoding="utf-8") for p in out.rglob("*.json")
    )


def test_the_sample_registry_still_runs_locally_when_asked(
    build: ModuleType, tmp_path: Path
) -> None:
    out = tmp_path / "out"

    feed = feed_with_sample_lookalike(tmp_path)

    code = build.main(["--ocds", str(feed), "--out", str(out), "--sample-registry"])

    assert code == 0
    match = published_details(out)[0]["supplier_match"]
    assert isinstance(match, dict) and match["source"] == "sample"


def cipc_feed(tmp_path: Path) -> Path:
    feed = tmp_path / "cipc_feed.jsonl"
    feed.write_text(
        '{"ocid":"ocds-9t57fa-1","buyer":{"id":"1","name":"Fictional Dept"},'
        '"tender":{"title":"Fictional tender","tenderPeriod":{"endDate":"2025-03-14"}},'
        '"awards":[{"id":"1","suppliers":[{"id":"900001","name":"Fictional Supplies"}],'
        '"value":{"amount":1000,"currency":"ZAR"}}]}\n',
        encoding="utf-8",
    )
    return feed


def cipc_dir(tmp_path: Path, registered: str) -> Path:
    d = tmp_path / "cipc"
    d.mkdir()
    (d / "companies.csv").write_text(
        "company_id,cipc_name,registration_number,registration_date,status,industry,"
        "annual_return_dates,checked_on\n"
        f"etenders:900001,FICTIONAL SUPPLIES (PTY) LTD,2025/000123/07,{registered},"
        "In Business,Wholesale trade,,2026-10-27\n",
        encoding="utf-8",
    )
    (d / "directors.csv").write_text(
        "company_id,director_id,full_name,appointed,resigned\n"
        "etenders:900001,dir-0001,A. Fictional Person,2025-02-20,\n",
        encoding="utf-8",
    )
    return d


def test_cipc_data_makes_the_company_rules_run(build: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "out"
    # Registered 22 days before the tender closed: R2 (under 30 days) must fire.
    cipc = cipc_dir(tmp_path, "2025-02-20")

    code = build.main(["--ocds", str(cipc_feed(tmp_path)), "--out", str(out), "--cipc", str(cipc)])

    assert code == 0
    (detail,) = published_details(out)
    rules = {r["rule_id"]: r for r in detail["breakdown"]}  # type: ignore[attr-defined]
    assert rules["R2"]["fired"] is True
    assert rules["R1"]["evaluated"] is True
    assert rules["R4"]["evaluated"] is True
    published = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*.json"))
    assert "A. Fictional Person" not in published


def test_without_cipc_the_company_rules_stay_not_evaluated(
    build: ModuleType, tmp_path: Path
) -> None:
    out = tmp_path / "out"

    code = build.main(["--ocds", str(cipc_feed(tmp_path)), "--out", str(out)])

    assert code == 0
    (detail,) = published_details(out)
    rules = {r["rule_id"]: r for r in detail["breakdown"]}  # type: ignore[attr-defined]
    assert rules["R2"]["evaluated"] is False


def test_bad_cipc_data_stops_the_build(
    build: ModuleType, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    out = tmp_path / "out"
    cipc = cipc_dir(tmp_path, "not-a-date")

    code = build.main(["--ocds", str(cipc_feed(tmp_path)), "--out", str(out), "--cipc", str(cipc)])

    assert code == 2
    assert "not a YYYY-MM-DD date" in caplog.text
    assert not out.exists()

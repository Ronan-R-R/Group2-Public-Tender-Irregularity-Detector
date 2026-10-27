"""Log safety of scripts/build_dashboard_data.py."""

import importlib.util
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

    described = build.describe_db_error(err.value)

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

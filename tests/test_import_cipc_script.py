"""scripts/import_cipc.py failure paths that need no database."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_cipc.py"
EXAMPLES = str(Path(__file__).resolve().parents[1] / "examples" / "cipc")


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("import_cipc", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_needs_a_database_url(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert script.main(["--cipc", EXAMPLES]) == 2
    assert "DATABASE_URL" in caplog.text


def test_bad_files_are_rejected_before_connecting(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Unresolvable host: reaching it would fail differently, proving no connection was tried.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:pw@db.example.test/postgres")
    (tmp_path / "companies.csv").write_text("wrong,header\n", encoding="utf-8")

    assert script.main(["--cipc", str(tmp_path)]) == 2
    assert "nothing was imported" in caplog.text
    assert "header must be exactly" in caplog.text


def test_an_unreachable_database_is_reported_without_the_password(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:Fict10nalPw@db.example.test/postgres")

    assert script.main(["--cipc", EXAMPLES]) == 3
    assert "import failed, nothing was committed" in caplog.text
    assert "Fict10nalPw" not in caplog.text

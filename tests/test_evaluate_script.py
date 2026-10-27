"""scripts/evaluate_detection.py end to end on a tiny synthetic feed."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_detection.py"
FEED = (
    '{"ocid":"ocds-9t57fa-1","buyer":{"id":"1","name":"Fictional Dept"},'
    '"tender":{"title":"Fictional tender",'
    '"procurementMethodDetails":"Request for Bid(Open-Tender)"},'
    '"awards":[{"id":"1","suppliers":[{"id":"100","name":"Fictional Supplier"}],'
    '"value":{"amount":1000000,"currency":"ZAR"}}]}'
)


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate_detection", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_writes_a_report_with_every_section(script: ModuleType, tmp_path: Path) -> None:
    feed = tmp_path / "feed.jsonl"
    feed.write_text(FEED + "\n", encoding="utf-8")
    out = tmp_path / "report" / "evaluation.md"

    code = script.main(["--ocds", str(feed), "--out", str(out)])

    assert code == 0
    text = out.read_text(encoding="utf-8")
    for heading in ("## Dataset", "## Rules", "## Scores", "## Isolation Forest", "## Limits"):
        assert heading in text
    assert "| Awards scored | 1 |" in text
    assert "Not enough priced awards" in text


def test_a_missing_feed_is_an_error(script: ModuleType, tmp_path: Path) -> None:
    code = script.main(["--ocds", str(tmp_path / "absent.jsonl"), "--out", str(tmp_path / "x.md")])

    assert code == 2
    assert not (tmp_path / "x.md").exists()

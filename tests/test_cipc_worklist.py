"""scripts/cipc_worklist.py on a small synthetic feed."""

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cipc_worklist.py"


@pytest.fixture(scope="module")
def worklist() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cipc_worklist", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release(n: int, buyer: str, supplier: str) -> str:
    return json.dumps(
        {
            "ocid": f"ocds-9t57fa-{n}",
            "buyer": {"id": buyer, "name": f"Fictional Dept {buyer}"},
            "tender": {"title": f"Fictional tender {n}"},
            "awards": [
                {"id": "1", "suppliers": [{"id": supplier, "name": f"Supplier {supplier}"}]}
            ],
        }
    )


def test_ranks_by_repeat_wins_from_one_buyer(worklist: ModuleType, tmp_path: Path) -> None:
    # 101: 3 awards from one buyer. 102: 4 awards spread over 4 buyers.
    rows = [release(i, "1", "101") for i in range(3)]
    rows += [release(10 + i, str(i), "102") for i in range(4)]
    rows += [release(20, "1", "103")]
    feed = tmp_path / "feed.jsonl"
    feed.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = tmp_path / "data" / "cipc" / "worklist.csv"

    code = worklist.main(["--ocds", str(feed), "--out", str(out), "--top", "2"])

    assert code == 0
    with out.open(encoding="utf-8", newline="") as handle:
        ranked = list(csv.DictReader(handle))
    assert [r["company_id"] for r in ranked] == ["etenders:101", "etenders:102"]
    assert ranked[0]["most_from_one_buyer"] == "3"
    assert ranked[0]["top_buyers"] == "Fictional Dept 1 (3)"


def test_rejects_a_bad_top_and_a_missing_feed(worklist: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "w.csv"

    assert worklist.main(["--ocds", str(tmp_path / "x"), "--out", str(out), "--top", "0"]) == 2
    assert worklist.main(["--ocds", str(tmp_path / "x"), "--out", str(out)]) == 2
    assert not out.exists()

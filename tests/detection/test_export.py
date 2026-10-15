import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from detection import export
from detection.anomaly import AnomalySignal
from detection.models import Company, RuleResult, Severity, Tender
from detection.rules import RULES
from detection.scorer import score

TF = Callable[..., Tender]
CF = Callable[..., Company]
NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
SOURCE = {"name": "test"}


def scored(
    make_tender: TF,
    make_company: CF,
    tender_id: str,
    results: list[RuleResult],
    value: str = "1000000",
) -> export.ScoredAward:
    tender = make_tender(tender_id=tender_id, award_value=Decimal(value))
    return export.ScoredAward(tender, make_company(), score(results))


def fire(rule_id: str, severity: Severity, **evidence: object) -> RuleResult:
    return RuleResult.fire(rule_id, f"{rule_id} title", severity, evidence)  # type: ignore[arg-type]


def test_index_ranks_by_level_then_score_then_value(make_tender: TF, make_company: CF) -> None:
    awards = [
        scored(make_tender, make_company, "low/1", [fire("R12", Severity.LOW)]),
        scored(
            make_tender,
            make_company,
            "alert/1",
            [fire(f"R{i}", Severity.CRITICAL) for i in (1, 2, 3)],
        ),
        scored(
            make_tender,
            make_company,
            "flag/big",
            [fire("R1", Severity.CRITICAL), fire("R2", Severity.CRITICAL)],
            "9000000",
        ),
        scored(
            make_tender,
            make_company,
            "flag/small",
            [fire("R1", Severity.CRITICAL), fire("R2", Severity.CRITICAL)],
            "10",
        ),
    ]

    index, _ = export.build(awards, RULES, NOW, SOURCE)

    rows = index["awards"]
    assert isinstance(rows, list)
    assert [r["id"] for r in rows if isinstance(r, dict)] == [
        "alert/1",
        "flag/big",
        "flag/small",
        "low/1",
    ]


def test_private_evidence_is_never_exported(make_tender: TF, make_company: CF) -> None:
    pep = RuleResult.fire(
        "R6",
        "PEP",
        Severity.CRITICAL,
        {"director_id": "dir-9f2c"},
        private_evidence={"director_name": "A. Fictional Person"},
        needs_review=True,
    )
    award = scored(make_tender, make_company, "t/1", [pep])

    index, shards = export.build([award], RULES, NOW, SOURCE)
    blob = json.dumps([index, shards])

    assert "A. Fictional Person" not in blob
    assert "director_name" not in blob
    assert "dir-9f2c" in blob


def test_comparables_only_kept_on_fired_rules(make_tender: TF, make_company: CF) -> None:
    comps = [{"tender_id": "x", "award_value": "1"}]
    high = RuleResult.fire(
        "R10",
        "high",
        Severity.HIGH,
        {"robust_z": 3.1, "comparables": comps},  # type: ignore[dict-item]
    )
    low = RuleResult.clear(
        "R11",
        "low",
        Severity.MEDIUM,
        {"robust_z": 3.1, "comparables": comps},  # type: ignore[dict-item]
    )
    award = scored(make_tender, make_company, "t/1", [high, low])

    _, shards = export.build([award], RULES, NOW, SOURCE)
    # Round-trip through JSON: the test reads the file shape a browser sees.
    record = json.loads(json.dumps(shards))[export.shard_of("t/1")]["t/1"]
    by_rule = {b["rule_id"]: b for b in record["breakdown"]}

    assert "comparables" in by_rule["R10"]["evidence"]
    assert "comparables" not in by_rule["R11"]["evidence"]
    assert by_rule["R11"]["evidence"]["robust_z"] == 3.1


def test_each_award_lands_in_the_shard_its_index_row_names(
    make_tender: TF, make_company: CF
) -> None:
    awards = [scored(make_tender, make_company, f"t/{i}", []) for i in range(40)]

    index, shards = export.build(awards, RULES, NOW, SOURCE)

    rows = index["awards"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        assert row["id"] in shards[str(row["shard"])]


def test_summary_and_catalogue(make_tender: TF, make_company: CF) -> None:
    awards = [
        scored(make_tender, make_company, "a/1", [fire("R7", Severity.MEDIUM)]),
        scored(
            make_tender,
            make_company,
            "a/2",
            [RuleResult.not_evaluated("R7", "t", Severity.MEDIUM, "x")],
        ),
    ]

    index, _ = export.build(awards, RULES, NOW, SOURCE)

    assert index["summary"] == {
        "awards": 2,
        "by_level": {"none": 2},
        "fired": {"R7": 1},
        "not_evaluated": {"R7": 1},
    }
    assert index["thresholds"] == {"flag": 50, "alert": 75, "max": 100}
    catalogue = index["rules"]
    assert isinstance(catalogue, list)
    assert [c["id"] for c in catalogue if isinstance(c, dict)] == [r.rule_id for r in RULES]
    assert index["generated_at"] == "2026-10-12T09:00:00+00:00"


def test_rejects_duplicate_ids_and_naive_timestamps(make_tender: TF, make_company: CF) -> None:
    a = scored(make_tender, make_company, "dup/1", [])

    with pytest.raises(ValueError, match="duplicate"):
        export.build([a, a], RULES, NOW, SOURCE)
    with pytest.raises(ValueError, match="timezone"):
        export.build([a], RULES, datetime(2026, 10, 12), SOURCE)


def test_write_replaces_previous_output(tmp_path: Path, make_tender: TF, make_company: CF) -> None:
    out = tmp_path / "data"
    (out / "details").mkdir(parents=True)
    (out / "details" / "stale.json").write_text("{}")
    index, shards = export.build([scored(make_tender, make_company, "t/1", [])], RULES, NOW, SOURCE)

    export.write(out, index, shards)

    assert not (out / "details" / "stale.json").exists()
    assert json.loads((out / "index.json").read_text(encoding="utf-8"))["summary"]["awards"] == 1
    assert len(list((out / "details").iterdir())) == 1


def test_row_fields(make_tender: TF, make_company: CF) -> None:
    tender = make_tender(tender_id="t/1", close_date=date(2025, 3, 14), award_value=Decimal("5.50"))
    award = export.ScoredAward(tender, make_company(name="Fictional Co"), score([]))

    row = export.index_row(award)

    assert row["supplier"] == "Fictional Co"
    assert row["supplier_id"] == tender.supplier_id
    assert row["buyer_id"] == tender.buyer_id
    assert row["value"] == "5.50"
    assert row["close_date"] == "2025-03-14"
    assert row["shard"] == export.shard_of("t/1")
    assert row["anomaly_pct"] is None


def test_anomaly_signal_is_exported_beside_the_score(make_tender: TF, make_company: CF) -> None:
    signal = AnomalySignal("t/1", 97.5, 1_000_000.0, 2_000_000.0, 1.2, 0.9)
    award = export.ScoredAward(make_tender(tender_id="t/1"), make_company(), score([]), signal)

    index, shards = export.build([award], RULES, NOW, SOURCE)
    record = json.loads(json.dumps(shards))[export.shard_of("t/1")]["t/1"]

    rows = index["awards"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    assert rows[0]["anomaly_pct"] == 97.5
    assert rows[0]["score"] == 0
    assert record["anomaly"] == {
        "percentile": 97.5,
        "category_median": "1000000.00",
        "buyer_median": "2000000.00",
        "log_vs_category": 1.2,
        "log_vs_buyer": 0.9,
    }

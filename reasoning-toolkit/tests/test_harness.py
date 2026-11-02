import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness import load_lane_output, run_comparison  # noqa: E402

from reasoning_servers.ledger import Ledger  # noqa: E402

PROBLEM = {
    "problem_id": "p1",
    "set_id": "s",
    "raw": "does a and a->b give b?",
    "parsed": '{"premises": ["a", "a -> b"], "conclusion": "b"}',
    "op": "entails",
    "source": "test",
}


def test_harness_records_one_row_per_lane(tmp_path):
    led = Ledger(str(tmp_path / "l.db"))
    lanes = {
        "local": {"verdict": "entails", "reasoning": "z3"},
        "subagent": {"verdict": "entails", "reasoning": "...", "model_id": "m"},
    }
    run_comparison("formal-logic", PROBLEM, lanes, ledger=led)
    rows = led.conn.execute(
        "SELECT lane, kind, output_hash FROM runs WHERE problem_id='p1'"
    ).fetchall()
    assert len(rows) == 2
    kinds = {r["lane"]: r["kind"] for r in rows}
    assert kinds["local"] == "measured"
    assert kinds["subagent"] == "asserted"
    assert all(r["output_hash"] for r in rows)


def test_harness_report_flags_divergence(tmp_path):
    led = Ledger(str(tmp_path / "l.db"))
    lanes = {"local": {"verdict": "entails"}, "subagent": {"verdict": "does_not_entail"}}
    report = run_comparison("formal-logic", PROBLEM, lanes, ledger=led)
    assert report["comparison"]["lanes"]["subagent"]["label"] == "incorrect"


def test_harness_handles_unparseable_subagent(tmp_path):
    bad = tmp_path / "subagent.json"
    bad.write_text("not json {")
    out = load_lane_output(str(bad))
    assert out["verdict"] == "unparseable"

    led = Ledger(str(tmp_path / "l.db"))
    lanes = {"local": {"verdict": "entails"}, "subagent": out}
    run_comparison("formal-logic", PROBLEM, lanes, ledger=led)
    row = led.conn.execute(
        "SELECT verdict FROM runs WHERE lane='subagent'"
    ).fetchone()
    assert row["verdict"] == "unparseable"


def test_harness_tolerates_unavailable_lane(tmp_path):
    led = Ledger(str(tmp_path / "l.db"))
    lanes = {
        "local": {"verdict": "entails"},
        "subagent": {"verdict": "entails"},
        "remote": {"verdict": "unavailable"},
    }
    report = run_comparison("formal-logic", PROBLEM, lanes, ledger=led)
    assert "metrics" in report  # the run completed
    assert report["metrics"]["subagent"]["agreement"] == 1.0

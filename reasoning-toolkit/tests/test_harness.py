import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness import (  # noqa: E402
    load_lane_output,
    run_comparison,
    run_got_comparison,
    score_adherence,
)

from reasoning_servers.graph_of_thought import replay_results  # noqa: E402
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


# --- graph-of-thought rule-adherence (Task 10) ---
_GOT_OPS = [
    {"op": "seed", "session_id": "s", "problem": "p"},
    {"op": "generate", "parent_id": "n0", "thoughts": ["a", "b"]},
    {"op": "score", "node_id": "n1", "score": 0.15},
    {"op": "score", "node_id": "n2", "score": 0.8},
    {"op": "aggregate", "parent_ids": ["n2"], "synthesis": "m"},
]


def test_adherence_perfect_on_valid_trace():
    claims = [{}, {}, {"pruned": True}, {"pruned": False}, {}]
    res = score_adherence(claims, replay_results(_GOT_OPS))
    assert res["adherence"] == 1.0
    assert res["violations"] == []


def test_adherence_detects_violation():
    ops = [
        {"op": "seed", "session_id": "s", "problem": "p"},
        {"op": "generate", "parent_id": "n0", "thoughts": ["a", "b"]},
        {"op": "aggregate", "parent_ids": ["n1"], "synthesis": "m"},
        {"op": "refine", "node_id": "n1", "improved_content": "x"},  # must be refused
    ]
    claims = [{}, {}, {}, {"refused": False}]  # critic wrongly claims it succeeded
    res = score_adherence(claims, replay_results(ops))
    assert res["adherence"] < 1.0
    assert any(v["key"] == "refused" for v in res["violations"])


def test_got_scores_recorded_asserted(tmp_path):
    led = Ledger(str(tmp_path / "l.db"))
    problem = {"problem_id": "g1", "set_id": "s", "raw": "r", "parsed": "{}",
               "op": "replay", "source": "t"}
    lanes = {"subagent": {"ops": _GOT_OPS,
                          "claims": [{}, {}, {"pruned": True}, {"pruned": False}, {}],
                          "scores": {"n1": 0.15, "n2": 0.8}, "synthesis": "m",
                          "model_id": "m"}}
    run_got_comparison(problem, lanes, led)
    kinds = {r["op"]: r["kind"] for r in led.conn.execute(
        "SELECT op, kind FROM runs WHERE problem_id='g1'")}
    assert kinds["replay"] == "measured"   # adherence is deterministic
    assert kinds["content"] == "asserted"  # scores/synthesis are judgment

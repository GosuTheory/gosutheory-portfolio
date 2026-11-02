"""Deterministic comparison harness: the scorekeeper is code, not an agent.

The agent-mediated part (dispatching the locked critic) happens in the skill;
this module only reads each lane's output, hashes it, records it, and renders the
comparison. No LLM is involved here.
"""
import hashlib
import json
import os

_VERDICT_DOMAIN = {
    "entails", "does_not_entail", "inconsistent_premises",
    "consistent", "inconsistent",
    "provable", "refuted", "unknown",
    "error", "unavailable", "unparseable",
    # graph-of-thought adherence lanes record their own verdicts too:
    "adherence",
}
# Only the propositional local Z3 lane is Measured ground truth; FOL (fol_prove)
# can return unknown, so even its local verdicts are Asserted.
_PROP_OPS = {"entails", "check_consistency"}
_ORACLE_LANE = {"formal-logic": "local", "graph-of-thought": None}


def _sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_lane_output(path):
    """Read a lane's output file; non-JSON or no verdict -> unparseable."""
    raw = open(path, "rb").read()
    output_hash = _sha256(raw)
    try:
        obj = json.loads(raw)
        verdict = obj.get("verdict")
        if not isinstance(verdict, str):
            raise ValueError("no verdict")
        obj["output_hash"] = output_hash
        return obj
    except (ValueError, AttributeError):
        return {"verdict": "unparseable", "reasoning": "output was not valid JSON with a verdict",
                "output_hash": output_hash}


def _kind(engine, lane, op):
    if engine == "formal-logic" and lane == "local" and op in _PROP_OPS:
        return "measured"
    return "asserted"


def run_comparison(engine, problem, lane_outputs, ledger=None):
    """Register the problem, record every lane, and return comparison + metrics.

    `lane_outputs` maps lane -> {"verdict", "reasoning"?, "output_hash"?,
    "model_id"?, "latency_ms"?}. `ledger` is injected for tests; otherwise a
    Ledger is opened from REASONING_LEDGER_DB.
    """
    if ledger is None:  # pragma: no cover
        from reasoning_servers.ledger import Ledger
        ledger = Ledger(os.environ.get("REASONING_LEDGER_DB", "ledger.db"))

    pid = problem["problem_id"]
    op = problem.get("op", "entails")
    parsed = problem.get("parsed", "")
    input_hash = _sha256(parsed)
    oracle_lane = _ORACLE_LANE.get(engine)

    ledger.register_problem(pid, engine, problem.get("set_id"), problem.get("raw", ""),
                            parsed, problem.get("source"))

    for lane, out in lane_outputs.items():
        verdict = out.get("verdict", "unparseable")
        if verdict not in _VERDICT_DOMAIN:
            verdict = "unparseable"
        ledger.record_run(
            pid, engine, lane, op, input_hash,
            out.get("output_hash") or _sha256(json.dumps(out, sort_keys=True)),
            verdict, out.get("reasoning", ""), out.get("latency_ms"),
            out.get("model_id"), _kind(engine, lane, op),
            1 if lane == oracle_lane else 0,
        )

    comparison = ledger.compare(pid)
    metrics = {
        lane: ledger.metrics(engine, lane, problem.get("set_id"))
        for lane in lane_outputs
        if lane != oracle_lane
    }
    return {"problem_id": pid, "comparison": comparison, "metrics": metrics,
            "report": _render(engine, comparison, metrics)}


def score_adherence(claimed, replayed):
    """Did the critic's claimed rule-outcomes match the deterministic replay?

    `claimed[i]` may carry `pruned`/`refused` claims; `replayed[i]` is the actual
    op result. Adherence is Measured (replay is deterministic); the thought
    content and scores themselves stay Asserted and are not graded here.
    """
    checks = 0
    violations = []
    for i, claim in enumerate(claimed):
        actual = replayed[i] if i < len(replayed) else {}
        for key in ("pruned", "refused"):
            if key in claim:
                checks += 1
                actual_val = bool(actual.get(key, False))
                if bool(claim[key]) != actual_val:
                    violations.append({"index": i, "op": actual.get("op"), "key": key,
                                       "claimed": bool(claim[key]), "actual": actual_val})
    adherence = 1.0 if checks == 0 else (checks - len(violations)) / checks
    return {"adherence": adherence, "violations": violations, "checks": checks}


def run_got_comparison(problem, lanes, ledger):
    """graph-of-thought lane comparison: adherence (measured) + content (asserted)."""
    from reasoning_servers.graph_of_thought import replay_results

    pid = problem["problem_id"]
    input_hash = _sha256(problem.get("parsed", ""))
    ledger.register_problem(pid, "graph-of-thought", problem.get("set_id"),
                            problem.get("raw", ""), problem.get("parsed", ""),
                            problem.get("source"))
    results = {}
    for lane, data in lanes.items():
        replayed = replay_results(data.get("ops", []))
        adh = score_adherence(data.get("claims", []), replayed)
        ledger.record_run(pid, "graph-of-thought", lane, "replay", input_hash,
                          _sha256(json.dumps(replayed, sort_keys=True)),
                          "adherence", json.dumps(adh), None, data.get("model_id"),
                          "measured", 0)
        content = {"scores": data.get("scores"), "synthesis": data.get("synthesis")}
        ledger.record_run(pid, "graph-of-thought", lane, "content", input_hash,
                          _sha256(json.dumps(content, sort_keys=True)),
                          "asserted", json.dumps(content), None, data.get("model_id"),
                          "asserted", 0)
        results[lane] = adh
    return {"problem_id": pid, "adherence": results}


def _render(engine, comparison, metrics):
    lines = [f"# Comparison — {engine} — {comparison['problem_id']}",
             f"oracle: {comparison['oracle_lane']} = {comparison['oracle_verdict']}", "",
             "| lane | verdict | label |", "| --- | --- | --- |"]
    for lane, info in comparison["lanes"].items():
        lines.append(f"| {lane} | {info['verdict']} | {info['label']} |")
    for lane, m in metrics.items():
        lines.append("")
        lines.append(f"{lane}: agreement {m['agreement']:.3f} "
                     f"(95% CI {m['wilson_lo']:.3f}-{m['wilson_hi']:.3f}), "
                     f"coverage {m['coverage']:.3f}, n={m['n']}, "
                     f"oracle_unknown={m['oracle_unknown']}")
    return "\n".join(lines)


def main(argv=None):  # pragma: no cover
    import sys
    argv = argv or sys.argv[1:]
    engine, problem_file, lane_dir = argv[0], argv[1], argv[2]
    problem = json.loads(open(problem_file, encoding="utf-8").read())
    lane_outputs = {}
    for name in os.listdir(lane_dir):
        if name.endswith(".json"):
            lane_outputs[name[:-5]] = load_lane_output(os.path.join(lane_dir, name))
    report = run_comparison(engine, problem, lane_outputs)
    print(report["report"])


if __name__ == "__main__":  # pragma: no cover
    main()

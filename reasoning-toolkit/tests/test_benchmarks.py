import json
from pathlib import Path

from reasoning_servers.formal_logic import entails, fol_prove

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def _rows(name):
    return [json.loads(line) for line in (BENCH / name).read_text().splitlines() if line.strip()]


def _verdict(row):
    if row["op"] == "fol_prove":
        return fol_prove(row["premises"], row["conclusion"])["verdict"]
    return entails(row["premises"], row["conclusion"])["verdict"]


def test_z3_reproduces_oracle_validation():
    rows = _rows("oracle_validation.jsonl")
    assert rows, "oracle validation set is empty"
    for r in rows:
        assert _verdict(r) == r["gold"], f"{r['id']}: got {_verdict(r)} expected {r['gold']}"


def test_benchmark_gold_selfconsistent():
    for r in _rows("subagent_propositional.jsonl"):
        got = entails(r["premises"], r["conclusion"])["verdict"]
        assert got == r["gold"], f"{r['id']}: Z3 {got} != stored {r['gold']}"


def test_benchmark_min_size_and_variety():
    rows = _rows("subagent_propositional.jsonl")
    assert len(rows) >= 40, f"only {len(rows)} items"
    golds = {r["gold"] for r in rows}
    assert "entails" in golds and "does_not_entail" in golds
    tags = set()
    for r in rows:
        tags.update(r.get("tags", []))
    for needed in ("modus_tollens_chain", "parity", "pigeonhole",
                   "nested_implication", "vacuous_truth"):
        assert needed in tags, f"missing a {needed} item"

"""ledger MCP server: append-only run store + compare + metrics.

Metrics are deliberately honest: agreement is computed only over problems whose
oracle gave a definite verdict and that the lane actually answered; coverage and
an all-problems figure sit beside it so a high rate on a dodged set is visible.
"""
import math
import os
import sqlite3
import time

# Oracle verdicts that are not usable ground truth (problem excluded from accuracy).
_INDEFINITE_ORACLE = {"unknown", "error", "unavailable", "unparseable"}
# Lane verdicts that are not a real answer (not counted as "answered").
_NOT_ANSWERED = {"unparseable", "error", "unavailable", "unknown"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
  problem_id  TEXT PRIMARY KEY,
  engine      TEXT NOT NULL,
  set_id      TEXT,
  raw         TEXT NOT NULL,
  parsed_json TEXT,
  source      TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT NOT NULL,
  problem_id  TEXT NOT NULL,
  engine      TEXT NOT NULL,
  lane        TEXT NOT NULL,
  op          TEXT NOT NULL,
  input_hash  TEXT NOT NULL,
  output_hash TEXT,
  verdict     TEXT NOT NULL,
  reasoning   TEXT,
  latency_ms  INTEGER,
  model_id    TEXT,
  kind        TEXT NOT NULL CHECK (kind IN ('measured','asserted')),
  oracle      INTEGER NOT NULL DEFAULT 0
);
"""


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half, centre + half)


class Ledger:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def register_problem(self, problem_id, engine, set_id, raw, parsed_json, source):
        self.conn.execute(
            "INSERT OR REPLACE INTO problems VALUES (?,?,?,?,?,?)",
            (problem_id, engine, set_id, raw, parsed_json, source),
        )
        self.conn.commit()
        return {"problem_id": problem_id}

    def record_run(self, problem_id, engine, lane, op, input_hash, output_hash,
                   verdict, reasoning, latency_ms, model_id, kind, oracle):
        self.conn.execute(
            "INSERT INTO runs (ts, problem_id, engine, lane, op, input_hash, "
            "output_hash, verdict, reasoning, latency_ms, model_id, kind, oracle) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), problem_id, engine,
             lane, op, input_hash, output_hash, verdict, reasoning, latency_ms,
             model_id, kind, int(oracle)),
        )
        self.conn.commit()
        return {"recorded": True}

    def _latest_runs(self, problem_id):
        """Latest run per lane for a problem (append-only; newest id wins)."""
        rows = self.conn.execute(
            "SELECT * FROM runs WHERE problem_id=? ORDER BY id", (problem_id,)
        ).fetchall()
        latest = {}
        oracle = None
        for r in rows:
            latest[r["lane"]] = r
            if r["oracle"]:
                oracle = r
        return latest, oracle

    def compare(self, problem_id):
        latest, oracle = self._latest_runs(problem_id)
        oracle_verdict = oracle["verdict"] if oracle else None
        definite = oracle_verdict is not None and oracle_verdict not in _INDEFINITE_ORACLE
        lanes = {}
        for lane, r in latest.items():
            if oracle and r["lane"] == oracle["lane"]:
                label = "oracle"
            elif not definite:
                label = "oracle_indeterminate"
            elif r["verdict"] in _NOT_ANSWERED:
                label = "not_answered"
            elif r["verdict"] == oracle_verdict:
                label = "correct"
            else:
                label = "incorrect"
            lanes[lane] = {"verdict": r["verdict"], "label": label}
        return {"problem_id": problem_id, "oracle_lane": oracle["lane"] if oracle else None,
                "oracle_verdict": oracle_verdict, "lanes": lanes}

    def metrics(self, engine, lane, set_id):
        pids = [row["problem_id"] for row in self.conn.execute(
            "SELECT problem_id FROM problems WHERE engine=? AND set_id=?",
            (engine, set_id))]
        n_eligible = answered = correct = oracle_unknown = 0
        for pid in pids:
            latest, oracle = self._latest_runs(pid)
            if oracle is None:
                continue
            ov = oracle["verdict"]
            if ov == "unknown":
                oracle_unknown += 1
            if ov in _INDEFINITE_ORACLE:
                continue
            n_eligible += 1
            lane_run = latest.get(lane)
            if lane_run is None or lane_run["verdict"] in _NOT_ANSWERED:
                continue
            answered += 1
            if lane_run["verdict"] == ov:
                correct += 1
        lo, hi = _wilson(correct, answered)
        return {
            "engine": engine, "lane": lane, "set_id": set_id,
            "n": n_eligible,
            "answered": answered,
            "coverage": (answered / n_eligible) if n_eligible else 0.0,
            "agreement": (correct / answered) if answered else 0.0,
            "wilson_lo": lo,
            "wilson_hi": hi,
            "answered_correct_over_all": (correct / n_eligible) if n_eligible else 0.0,
            "oracle_unknown": oracle_unknown,
        }


# --- MCP wiring (thin shell; not exercised by unit tests) ---
def main():  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    led = Ledger(os.environ.get("REASONING_LEDGER_DB", "ledger.db"))
    mcp = FastMCP("ledger")
    mcp.tool(name="register_problem")(led.register_problem)
    mcp.tool(name="record_run")(led.record_run)
    mcp.tool(name="compare")(led.compare)
    mcp.tool(name="metrics")(led.metrics)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

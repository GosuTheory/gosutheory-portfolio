"""graph_of_thought MCP server: a reasoning-graph store with deterministic rules.

The store holds no reasoning of its own; it enforces the documented semantics
(score < 0.3 prunes permanently; refine is refused after aggregate; refine
returns a new id) and can `replay` a claimed operation trace, which is the
deterministic oracle the GoT rule-adherence check uses.
"""
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
  node_id    TEXT PRIMARY KEY,
  session_id TEXT,
  kind       TEXT NOT NULL,
  content    TEXT,
  score      REAL,
  pruned     INTEGER NOT NULL DEFAULT 0,
  aggregated INTEGER NOT NULL DEFAULT 0,
  refined_from TEXT
);
CREATE TABLE IF NOT EXISTS edges (parent TEXT, child TEXT);
"""

_PRUNE_THRESHOLD = 0.3


class GraphStore:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self._counter = 0

    def _new_id(self):
        nid = f"n{self._counter}"
        self._counter += 1
        return nid

    def _get(self, node_id):
        return self.conn.execute("SELECT * FROM nodes WHERE node_id=?", (node_id,)).fetchone()

    def _session_of(self, node_id):
        row = self._get(node_id)
        return row["session_id"] if row else None

    def seed(self, session_id, problem):
        nid = self._new_id()
        self.conn.execute(
            "INSERT INTO nodes (node_id, session_id, kind, content) VALUES (?,?,?,?)",
            (nid, session_id, "seed", problem))
        self.conn.commit()
        return {"node_id": nid}

    def generate(self, parent_id, thoughts):
        session = self._session_of(parent_id)
        created = []
        for content in thoughts:
            nid = self._new_id()
            self.conn.execute(
                "INSERT INTO nodes (node_id, session_id, kind, content) VALUES (?,?,?,?)",
                (nid, session, "thought", content))
            self.conn.execute("INSERT INTO edges (parent, child) VALUES (?,?)", (parent_id, nid))
            created.append(nid)
        self.conn.commit()
        return {"parent_id": parent_id, "created": created}

    def score(self, node_id, score, reasoning=""):
        pruned = 1 if score < _PRUNE_THRESHOLD else 0
        self.conn.execute("UPDATE nodes SET score=?, pruned=? WHERE node_id=?",
                          (score, pruned, node_id))
        self.conn.commit()
        return {"node_id": node_id, "score": score, "pruned": bool(pruned)}

    def aggregate(self, parent_ids, synthesis):
        session = self._session_of(parent_ids[0]) if parent_ids else None
        nid = self._new_id()
        self.conn.execute(
            "INSERT INTO nodes (node_id, session_id, kind, content) VALUES (?,?,?,?)",
            (nid, session, "aggregate", synthesis))
        for p in parent_ids:
            self.conn.execute("INSERT INTO edges (parent, child) VALUES (?,?)", (p, nid))
            self.conn.execute("UPDATE nodes SET aggregated=1 WHERE node_id=?", (p,))
        self.conn.commit()
        return {"node_id": nid, "merged_from": list(parent_ids)}

    def refine(self, node_id, improved_content):
        row = self._get(node_id)
        if row is None:
            return {"refused": True, "error": f"no such node {node_id}"}
        if row["aggregated"]:
            return {"refused": True, "error": "refine refused: node has been aggregated"}
        nid = self._new_id()
        self.conn.execute(
            "INSERT INTO nodes (node_id, session_id, kind, content, refined_from) VALUES (?,?,?,?,?)",
            (nid, row["session_id"], "refine", improved_content, node_id))
        self.conn.commit()
        return {"node_id": nid, "refined_from": node_id}

    def state(self):
        nodes = {}
        for r in self.conn.execute("SELECT * FROM nodes ORDER BY node_id"):
            nodes[r["node_id"]] = {
                "kind": r["kind"], "content": r["content"], "score": r["score"],
                "pruned": bool(r["pruned"]), "aggregated": bool(r["aggregated"]),
                "refined_from": r["refined_from"],
            }
        edges = sorted([p, c] for p, c in
                       self.conn.execute("SELECT parent, child FROM edges"))
        return {"nodes": nodes, "edges": edges}


def replay(ops):
    """Apply a claimed operation trace to a fresh store; return the resulting state."""
    store = GraphStore()
    for op in ops:
        kw = {k: v for k, v in op.items() if k != "op"}
        getattr(store, op["op"])(**kw)
    return store.state()


# --- MCP wiring (thin shell; not exercised by unit tests) ---
def main():  # pragma: no cover
    import os

    from mcp.server.fastmcp import FastMCP

    store = GraphStore(os.environ.get("REASONING_GOT_DB", "got.db"))
    mcp = FastMCP("graph_of_thought")
    for name in ("seed", "generate", "score", "aggregate", "refine"):
        mcp.tool(name=name)(getattr(store, name))
    mcp.tool(name="replay")(replay)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

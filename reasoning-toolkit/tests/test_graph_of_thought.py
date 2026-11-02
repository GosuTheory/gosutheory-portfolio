from reasoning_servers.graph_of_thought import GraphStore, replay


def test_score_below_threshold_prunes():
    g = GraphStore()
    root = g.seed("s", "problem")["node_id"]
    child = g.generate(root, ["idea"])["created"][0]
    assert g.score(child, 0.15, "weak")["pruned"] is True


def test_refine_after_aggregate_refused():
    g = GraphStore()
    root = g.seed("s", "p")["node_id"]
    ids = g.generate(root, ["a", "b"])["created"]
    g.aggregate(ids, "merged")
    assert g.refine(ids[0], "better").get("refused") is True


def test_refine_returns_new_id():
    g = GraphStore()
    root = g.seed("s", "p")["node_id"]
    child = g.generate(root, ["a"])["created"][0]
    res = g.refine(child, "better")
    assert res["node_id"] != child
    assert res["refined_from"] == child


def test_aggregate_merges():
    g = GraphStore()
    root = g.seed("s", "p")["node_id"]
    ids = g.generate(root, ["a", "b", "c"])["created"]
    res = g.aggregate(ids, "synthesis")
    assert res["merged_from"] == ids
    assert res["node_id"]


def test_replay_matches_direct_calls():
    ops = [
        {"op": "seed", "session_id": "s", "problem": "p"},
        {"op": "generate", "parent_id": "n0", "thoughts": ["a", "b"]},
        {"op": "score", "node_id": "n1", "score": 0.15},
        {"op": "score", "node_id": "n2", "score": 0.9},
        {"op": "aggregate", "parent_ids": ["n2"], "synthesis": "m"},
    ]
    direct = GraphStore()
    for op in ops:
        kw = {k: v for k, v in op.items() if k != "op"}
        getattr(direct, op["op"])(**kw)
    assert replay(ops) == direct.state()

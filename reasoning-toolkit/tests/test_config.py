import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # reasoning-toolkit/


def test_config_lists_both_engines_with_oracle():
    from reasoning_servers import load_config

    cfg = load_config(str(ROOT / "config" / "reasoning-config.json"))
    assert cfg["formal-logic"]["oracle"] == "local"
    assert cfg["graph-of-thought"]["oracle"] is None
    for engine in ("formal-logic", "graph-of-thought"):
        assert cfg[engine]["lanes"] == ["local", "subagent", "remote"]


def test_mcp_json_valid():
    data = json.loads((ROOT / ".mcp.json").read_text())
    servers = data["mcpServers"]
    for name in ("formal_logic", "graph_of_thought", "ledger"):
        assert name in servers

import re
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1] / "agents"
CHEAT_TOOLS = {"Bash", "Read", "WebFetch", "WebSearch", "Task"}


def _frontmatter(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{path} has no frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def _as_set(val):
    return {t.strip() for t in val.split(",") if t.strip()}


def test_formal_logic_critic_has_no_cheat_tools():
    fm = _frontmatter(AGENTS / "formal-logic-critic.md")
    allow = _as_set(fm.get("tools", ""))
    deny = _as_set(fm.get("disallowedTools", ""))
    # The binding guarantee: the allowlist contains nothing that can compute or
    # fetch a verdict (only Write, so the critic can emit its answer file).
    assert allow <= {"Write"}
    assert not (allow & CHEAT_TOOLS)
    # Defense in depth: the denylist bans every cheat path, including all MCP tools.
    assert CHEAT_TOOLS <= deny
    assert any(t.startswith("mcp__") for t in deny)

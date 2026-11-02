"""reasoning_servers: deterministic MCP servers for the reasoning-toolkit plugin."""
import json

_REQUIRED_ENGINES = ("formal-logic", "graph-of-thought")


def load_config(path):
    """Load and lightly validate reasoning-config.json.

    Returns the parsed dict. Raises ValueError if a required engine or its
    required keys (lanes, oracle) are missing.
    """
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for engine in _REQUIRED_ENGINES:
        if engine not in cfg:
            raise ValueError(f"reasoning-config.json missing engine: {engine}")
        entry = cfg[engine]
        for key in ("lanes", "oracle"):
            if key not in entry:
                raise ValueError(f"engine {engine} missing required key: {key}")
    return cfg

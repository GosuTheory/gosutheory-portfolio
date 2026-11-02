---
name: comparison-harness
description: Run an engine across its enabled lanes on one problem, then let the deterministic harness record and score them. The ONLY agent-mediated step is dispatching the locked critic; scorekeeping is code. Use for /reason-compare.
---

# comparison-harness

One rule governs this skill: **you dispatch the critic, you do not grade anyone.**
Grading (register, record, compare, metrics) is done by `scripts/harness.py` so the
scorekeeper is code, not an LLM.

## Steps

1. **Read config.** `config/reasoning-config.json` gives the engine's `lanes`, its
   `oracle`, and the `subagent.agent` to dispatch.

2. **Encode the problem.** For `formal-logic`, use the `formal-logic` skill to produce
   the fixed `{premises, conclusion}` + `op`. Build a problem dict:
   `{"problem_id", "set_id", "raw", "parsed": "<json string>", "op", "source"}`.
   Pick a stable `problem_id` (hash of `raw` is fine).

3. **Run each enabled lane**, writing each lane's result to `runs/<problem_id>/<lane>.json`:
   - `local` / `remote`: call the MCP tool, write its `{verdict, reasoning, ...}` to the file.
   - `subagent`: dispatch the configured critic agent (e.g. `formal-logic-critic`) and
     tell it to WRITE its JSON to `runs/<problem_id>/subagent.json`. The critic is
     tool-locked (no solver, no MCP, no Bash) — this is what makes its verdict a real
     measurement. Never hand it the oracle's answer or a gold file.
   - A lane with no token/endpoint is skipped; record `{"verdict": "unavailable"}`.

4. **Score with code.** Run:
   `python scripts/harness.py <engine> runs/<problem_id>/problem.json runs/<problem_id>/`
   (write the problem dict to `runs/<problem_id>/problem.json` first). The harness
   reads every `<lane>.json`, hashes it, records it, and prints the comparison +
   per-lane agreement (with CI and coverage).

5. **Report** the harness output. Where an oracle exists, say plainly which lanes
   matched it and which were caught out. Do not re-grade by hand.

## Why this shape

An MCP server cannot call the Task tool, so the critic dispatch must happen here, in
the agent. Everything else is deterministic Python precisely so the measurement does
not depend on an LLM's bookkeeping.

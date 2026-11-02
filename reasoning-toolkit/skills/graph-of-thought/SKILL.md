---
name: graph-of-thought
description: Run the graph-of-thought engine across lanes and score rule-adherence. There is no deterministic content oracle, so the measured number is whether a lane correctly enforced the graph rules it claimed to.
---

# graph-of-thought

This engine has **no oracle for reasoning content** — the scores a graph assigns
are judgment (Asserted). What it DOES have is a deterministic oracle for **rule
adherence**: the state-machine rules (prune `< 0.3`, no `refine` after
`aggregate`, `refine` yields a new id). That is the only thing measured here.

## Steps

1. **Pose the problem.** Build a problem dict with a stable `problem_id`, `set_id`,
   `raw`, `parsed`, `op: "replay"`, `source`.

2. **Run the lane(s).** For the `subagent` lane, dispatch the tool-locked
   `graph-of-thought-critic`. It maintains the graph in-context, enforcing the rules
   itself, and writes JSON with:
   - `ops`: the ordered operation trace it believes it performed,
   - `claims`: its claim about each op's rule outcome (`{"pruned": …}` / `{"refused": …}`),
   - `scores`, `synthesis`: its reasoning content (Asserted).
   The critic has no solver and no replay tool — the trace must be its own.

3. **Score with code.** `run_got_comparison` replays `ops` through the
   `graph_of_thought` engine and scores adherence = fraction of claims that match
   what the rules actually produce. Adherence is recorded **measured**; the scores
   and synthesis are recorded **asserted**. Never grade the content for correctness —
   there is nothing to be correct against, and saying so is the point of this engine.

4. **Report** adherence (with any violations) and show the claimed scores/synthesis
   plainly labelled as Asserted.

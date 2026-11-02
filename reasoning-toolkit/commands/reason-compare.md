---
description: Compare an engine's lanes (local oracle / subagent / remote) on one problem and record the scored result.
---

Run a lane comparison for the reasoning-toolkit.

**Arguments:** `$ARGUMENTS` — the engine (`formal-logic` or `graph-of-thought`)
followed by the problem, e.g.

```
/reason-compare formal-logic  If it rains the ground is wet. It rained. Is the ground wet?
```

Invoke the **comparison-harness** skill to execute this: encode the problem once,
run each enabled lane (dispatching the tool-locked critic for the subagent lane),
then let `scripts/harness.py` record and score the lanes. Report the harness's
comparison table and the agreement figure; do not grade by hand.

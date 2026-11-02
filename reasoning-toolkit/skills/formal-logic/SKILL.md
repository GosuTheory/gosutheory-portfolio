---
name: formal-logic
description: Parse a logic problem into a fixed {premises, conclusion} encoding and route it to the formal-logic lanes (local Z3, subagent critic, remote). Used by the comparison-harness.
---

# formal-logic

The job here is to turn a natural-language or semi-formal problem into ONE fixed
encoding that every lane then judges, so the comparison measures inference, not
formalization.

## 1. Parse (Asserted)

Produce `{ "premises": [ ... ], "conclusion": "..." }` in this notation:

- `~` not, `&` and, `|` or, `->` implies, `<->` iff.
- First-order: `forall X, (...)`, `exists X, (...)`, predicates `P(x)`, `R(x, y)`;
  constants are lowercase identifiers, bound variables are the quantified names.

Pick `op`:
- `entails` — propositional (atoms are whole propositions).
- `fol_prove` — the rule must quantify over individuals (use when "every/all/any X").
- `check_consistency` — "can these hold together?".

The parse is **Asserted**: record it with the problem. Everything downstream judges
exactly this encoding. Do not silently re-encode per lane.

## 2. Lanes

- `local` — call the `formal_logic` MCP tool for the chosen op. For propositional
  `entails`/`check_consistency` this is the Measured oracle (Z3 is complete there).
- `subagent` — dispatch the `formal-logic-critic` agent (see comparison-harness). It
  reasons without a solver; its agreement with `local` is the headline number.
- `remote` — the reasoning.services tool, only if `REASONING_SERVICES_TOKEN` is set;
  otherwise it is skipped and recorded `unavailable`.

Hand the lane outputs to the comparison-harness skill, which records and scores them.

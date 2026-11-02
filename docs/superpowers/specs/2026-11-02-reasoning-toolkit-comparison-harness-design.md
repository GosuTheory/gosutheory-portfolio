# Reasoning Toolkit — Comparison-Harness Vertical Slice

> **Status**: Design (approved for spec review)
> **Date**: 2026-11-02
> **Author**: GosuTheory (GT), with Claude Code
> **Scope**: Phase 1 vertical slice of a larger `reasoning-toolkit` Claude Code plugin

---

## 1. Purpose and motivation

### 1.1 What we are building
A standalone, movable Claude Code plugin, `reasoning-toolkit`, that re-implements the
reasoning.services engines so each engine can run through interchangeable **lanes**:

- `remote` — the hosted reasoning.services MCP endpoint (for engines we have trial access to),
- `local` — a small, deterministic, open-source rebuild we write ourselves,
- `subagent` — an LLM rebuild driven by Claude Code subagents.

The plugin's spine is a **comparison harness** that runs multiple lanes of the same engine on
the same input, records every lane's output to a results ledger, and reports where the lanes
agree, where they diverge, and — where an oracle lane exists — which lanes were wrong.

### 1.2 Why (the epistemic requirement)
The driving requirement is **"not dancing with robots."** The toolkit must produce claims that
can be checked against something that is *not* an LLM's opinion. This is the same discipline as
GT's Trace Ledger: *"put every formal move to a solver so the parts that aren't my judgment can
be checked without taking my word for any of it,"* and the Measured-vs-Asserted split that runs
down that document.

Concretely, success is a **number**: for an engine that has a deterministic oracle (formal
logic → Z3), the per-lane **agreement rate vs the oracle** across a known-answer test set. That
number quantifies how far an LLM lane can be trusted without the solver. Where no oracle exists
(graph-of-thought scoring), the harness must say so explicitly and record those outputs as
`asserted`, never dressing them up as measured.

### 1.3 Non-goals (this slice)
- No router (`reasoning-guide`) or orchestrator (`reasoning-chain`).
- No denied engines yet (`devils-advocate`, `decision-matrix`, `context-switcher`,
  `hindsight`, `structured-reflection`).
- No trace-ledger vector RAG / "ledger pointer" observability layer.
- No Ollama or external-API critic lanes — the chosen critic is Claude Code subagents.
- Not a portfolio feature; it merely lives in this repo's branch until lifted into its own repo.

---

## 2. Engines in scope

Only the two engines GT's Trace Ledger actually exercises ("the ones we know work"):

| Engine | Operations | Oracle? | Why it's in the slice |
| --- | --- | --- | --- |
| `formal-logic` | `entails`, `check_consistency`, `fol_prove` | **Yes — local Z3** | The keystone. A deterministic oracle makes the comparison objective: when the subagent lane disagrees with Z3, the robot was dancing. |
| `graph-of-thought` | `seed`, `generate`, `score`, `aggregate`, `refine` | **No** | The instructive contrast. Scores are GT's judgment (Asserted). Proves the harness works where nothing deterministic can check the output, and shows *where* robot-dancing hides (the scoring step). |

---

## 3. Architecture

### 3.1 Component inventory
Each component has one clear purpose, a defined interface, and explicit dependencies.

1. **Local MCP server: `formal_logic`** (Python + `z3-solver`)
   - *Does*: evaluates `entails`/`check_consistency` (propositional SAT refutation) and
     `fol_prove` (quantified, via Z3) and returns a structured verdict.
   - *Interface*: MCP tools `entails(premises, conclusion)`, `check_consistency(formulas)`,
     `fol_prove(premises, conclusion)`; each returns `{verdict, detail, model?/counterexample?}`.
   - *Depends on*: `z3-solver`, `mcp`. No network, no LLM, no state.

2. **Local MCP server: `graph_of_thought`** (Python + sqlite)
   - *Does*: holds a reasoning graph server-side and enforces the documented semantics —
     `score < 0.3` prunes a node permanently; `refine` is refused once a node has been merged
     (`aggregate`); `refine` returns a *new* node id.
   - *Interface*: MCP tools `seed(session_id, problem)`, `generate(parent_id, thoughts[])`,
     `score(node_id, score, reasoning)`, `aggregate(parent_ids[], synthesis)`,
     `refine(node_id, improved_content)`.
   - *Depends on*: `mcp`, stdlib `sqlite3`. No network, no LLM.

3. **Local MCP server: `ledger`** (Python + sqlite)
   - *Does*: append-only store of lane runs; computes agreement and oracle-labeled correctness.
   - *Interface*: MCP tools `record_run(...)`, `compare(problem_id)`, `agreement_rate(engine, lane)`,
     `register_problem(...)`, `query(...)`.
   - *Depends on*: `mcp`, stdlib `sqlite3`.

4. **Skill: `comparison-harness`** (markdown protocol, runs on the main agent)
   - *Does*: the orchestration contract — for a given engine + problem, determine enabled lanes
     from config, run each lane, record each to the ledger, call `compare`, and render the report.
   - *Depends on*: the three servers (for `local`/`remote` lanes and recording), the Agent/subagent
     tool (for the `subagent` lane), `reasoning-config.json`.

5. **Skill: `formal-logic`** (markdown protocol)
   - *Does*: how to parse a natural-language or semi-formal problem into `premises`/`conclusion`,
     how to route to each lane, and the exact subagent prompt for the `subagent` lane.

6. **Skill: `graph-of-thought`** (markdown protocol)
   - *Does*: the seed→generate→score→aggregate protocol and per-lane routing; the subagent-lane
     instructions for maintaining an in-context graph that returns the same structure.

7. **Command: `/reason-compare`** (markdown)
   - *Does*: entrypoint — `/reason-compare <engine> <problem>`; invokes the comparison-harness skill.

8. **Config: `reasoning-config.json`** — per-engine lane list, oracle designation, remote enable-gate.

9. **Plugin manifest + `.mcp.json`** — registers the three local servers and the remote
   reasoning.services server.

### 3.2 Why the subagent lane is orchestrated from a skill, not a server
A Claude Code MCP server process cannot call the Task/subagent tool — that tool exists only for
the main agent. Therefore the LLM (`subagent`) lane is driven by the **skill** on the main agent,
which dispatches a fresh, isolated subagent per lane per problem and then records the result via
the `ledger` server. The servers stay deterministic and stateless-except-for-storage; all LLM
behavior is in skills. Fresh-subagent-per-lane gives genuine context isolation (the property
reasoning.services only claims).

### 3.3 Proposed directory layout (built at implementation time, not now)
```
reasoning-toolkit/
├── .claude-plugin/plugin.json
├── .mcp.json
├── config/reasoning-config.json
├── commands/reason-compare.md
├── skills/
│   ├── comparison-harness/SKILL.md
│   ├── formal-logic/SKILL.md
│   └── graph-of-thought/SKILL.md
├── servers/reasoning_servers/
│   ├── __init__.py
│   ├── formal_logic.py
│   ├── graph_of_thought.py
│   ├── ledger.py
│   ├── _z3_encode.py          # shared premise/conclusion parsing for Z3
│   └── pyproject.toml         # single dependency surface
├── scripts/seed_examples.py   # load known-answer examples from the Trace Ledger
├── tests/
│   ├── test_formal_logic.py
│   ├── test_graph_of_thought.py
│   └── test_ledger.py
└── README.md
```
One Python package, one virtual environment, one install step — minimal setup friction.

---

## 4. Lane contract and the hybrid toggle

### 4.1 Operation contract (stable across lanes)
Every lane of an engine accepts the same operation inputs and returns a comparable result. For
`formal-logic.entails`:

- **Input**: `{ premises: string[], conclusion: string }` in the reasoning.services/Z3 surface
  syntax (operators `->`, `&`, `|`, `~`, `forall`, predicates `Name(x)`).
- **Output**: `{ verdict: "entails" | "does_not_entail" | "error", reasoning: string,
  counterexample?: object }`.

`fol_prove` output verdict ∈ `{ "provable", "refuted", "error" }`; `check_consistency` verdict ∈
`{ "consistent", "inconsistent", "error" }` with a `model?` when consistent. These mirror the
verdict vocabulary documented in the Trace Ledger (§6).

### 4.2 `reasoning-config.json`
```json
{
  "formal-logic": {
    "lanes": ["local", "subagent", "remote"],
    "oracle": "local",
    "remote": {
      "enabled_when": "token",
      "server": "reasoning_remote",
      "url_env": "REASONING_SERVICES_URL",
      "token_env": "REASONING_SERVICES_TOKEN"
    }
  },
  "graph-of-thought": {
    "lanes": ["local", "subagent", "remote"],
    "oracle": null,
    "remote": { "enabled_when": "token", "server": "reasoning_remote" }
  }
}
```

### 4.3 Lane selection semantics
- **Compare mode** (`/reason-compare`): run *all* lanes in `lanes[]` that are currently available.
- **Single-call `auto`**: prefer `oracle` → else `local` → else `remote` (if token present) → else `subagent`.
- A lane that is unavailable (no token, server down, trial lapsed) is **skipped**, recorded as
  `verdict=unavailable`, and never aborts the run. This is the "survives the token lapsing"
  property the Trace Ledger documents as a real event (2026-09-24 trial lapse).

---

## 5. Data flow — `/reason-compare formal-logic "<problem>"`

1. **Parse** — the `formal-logic` skill turns the problem into `{premises, conclusion}`. (This
   step may itself use the main agent's reasoning; the parse is recorded with the problem so the
   comparison is apples-to-apples across lanes.)
2. **Register** — `ledger.register_problem(problem_id, engine, raw, parsed_json, source)`.
3. **Run each enabled lane**:
   - `local` / `remote` → MCP tool call to the respective server.
   - `subagent` → dispatch a fresh subagent with the engine's subagent prompt; capture
     `{verdict, reasoning}` as JSON.
4. **Record** — `ledger.record_run(problem_id, engine, lane, op, input_hash, verdict, reasoning,
   latency_ms, kind, oracle)` where `kind` is `measured` for `local` formal-logic (Z3) and
   `asserted` for every LLM/`subagent` lane and all graph-of-thought lanes.
5. **Compare** — `ledger.compare(problem_id)` returns the agreement matrix. If the engine has an
   `oracle` lane (formal-logic → `local`/Z3), each non-oracle lane is labeled `correct` /
   `incorrect` against it. When `oracle` is `null` (graph-of-thought), `compare` reports
   **structural agreement only**: it diffs the lanes' *decisions* — which nodes were pruned
   (`score < 0.3`), which were aggregated, and node/edge counts — and sets the terminal syntheses
   side by side for a human to read. Every output stays marked `asserted`; no lane is labeled
   correct/incorrect because there is nothing deterministic to be correct against. That absence is
   itself the finding the contrast engine exists to show.
6. **Report** — the harness renders a table: lane × verdict × latency, the agreement/divergence
   summary, and (with an oracle) an explicit "lanes caught dancing" list.

### 5.1 Ledger schema (sqlite)
```sql
CREATE TABLE problems (
  problem_id TEXT PRIMARY KEY,
  engine     TEXT NOT NULL,
  raw        TEXT NOT NULL,
  parsed_json TEXT,
  source     TEXT            -- e.g. 'trace-ledger:pendulum', 'user'
);

CREATE TABLE runs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  problem_id TEXT NOT NULL REFERENCES problems(problem_id),
  engine     TEXT NOT NULL,
  lane       TEXT NOT NULL,          -- local | subagent | remote
  op         TEXT NOT NULL,          -- entails | fol_prove | ...
  input_hash TEXT NOT NULL,
  verdict    TEXT NOT NULL,          -- incl. 'error' | 'unavailable' | 'unparseable'
  reasoning  TEXT,
  latency_ms INTEGER,
  kind       TEXT NOT NULL CHECK (kind IN ('measured','asserted')),
  oracle     INTEGER NOT NULL DEFAULT 0
);
```

### 5.2 Headline metric
`agreement_rate(engine, lane)` = over all problems where both `lane` and the oracle produced a
non-error verdict, the fraction where they match. For `formal-logic.subagent` vs `local` (Z3)
this is the single number that answers "how much can the LLM's logic be trusted without a solver."

---

## 6. Subagent lane prompts (sketch)

**formal-logic / subagent** (deliberately solver-free):
> You are a logic engine. Given premises and a conclusion, decide whether the premises **entail**
> the conclusion. You may reason step by step but you may **not** invoke any external solver or
> tool. Return only JSON: `{"verdict": "entails" | "does_not_entail", "reasoning": "<short>"}`.

**graph-of-thought / subagent**:
> Maintain a reasoning graph for the given problem using the operations seed/generate/score/
> aggregate. Enforce: any node you score below 0.3 is pruned; a node cannot be refined after it
> is aggregated. Return the final graph as JSON (nodes, edges, scores, terminal synthesis).

Isolation: one fresh subagent per lane per problem — no shared context, no contamination.

---

## 7. Remote lane wiring

`.mcp.json` registers reasoning.services as an HTTP MCP server with
`Authorization: Bearer ${REASONING_SERVICES_TOKEN}` and base URL `${REASONING_SERVICES_URL}`.
Tool names observed in the Trace Ledger: `seed/generate/score/aggregate/refine` (graph) and
`entails/check_consistency/fol_prove` (logic).

**Assumption / open item**: the exact endpoint URL and auth are not in the ledger. The `local`
and `subagent` lanes need none of this, so the slice is fully buildable and testable without it.
The remote lane is wired last, when GT supplies the endpoint (likely liftable from
`~/.claude.json` if the reasoning.services marketplace plugin is installed). Until then the remote
lane records `unavailable` and the harness proceeds.

---

## 8. Error handling (mirrors the ledger's documented failure modes)

- **Z3 parse/syntax error** → structured result in the ledger's own `❌ Invalid Input` style,
  `verdict=error`. Regression test includes the HTML-escaped-ampersand case (`&amp;` vs `&`) from
  Trace Ledger §5.
- **Vacuous `consistent`** → `check_consistency` flags when the only satisfying model sets every
  atom false (the Part III footgun); the result notes it rather than reporting a clean pass.
- **Subagent returns non-JSON** → one stricter-prompt retry, then `verdict=unparseable`.
- **Remote refuses / token lapsed** → `verdict=unavailable`, run continues.
- **Ledger** is append-only; `input_hash` identifies re-runs while preserving history.

---

## 9. Testing strategy — the proof the toolkit constrains something

### 9.1 Oracle validation (Measured ground truth from the Trace Ledger)
Z3 `local` lane must reproduce GT's recorded verdicts:
- **Pendulum (§5)**: propositional encoding → `does_not_entail` with a counterexample;
  predicate (FOL) encoding → `provable`.
- **054 meta-theorem**: `provable` in its quantified form; supporting `~thing_ontology` and
  `fact -> ~truth` → `entails`.
- **040 T14**: both derivations → `entails`, no counterexample.
If Z3 matches these, the oracle is trustworthy; the whole comparison rests on this.

### 9.2 Agreement-rate run
Run `formal-logic.subagent` across the §9.1 examples and compute agreement vs Z3. The resulting
rate is the slice's headline deliverable.

### 9.3 graph-of-thought semantics (reproducibility, not correctness)
- `score(node, 0.15)` → node pruned, flagged in response.
- `refine` after `aggregate` → refused; `refine` otherwise → new node id.
- `aggregate(a,b,c)` → single merged node.

### 9.4 Harness + ledger
- Multi-lane run writes one `runs` row per lane; `compare` labels non-oracle lanes against the
  oracle; `agreement_rate` math is correct on a hand-checked fixture.

All tests run locally: no token, no paid API; subagent tests are the only ones needing a session.

---

## 10. Dependencies

- `z3-solver` (PyPI) — the solver. Version pinned and import-verified at implementation.
- `mcp` (Python MCP SDK) — server framework. Version pinned at implementation.
- stdlib `sqlite3` — graph + ledger storage.
- `sqlite-vec` — **deferred to the hindsight/RAG phase**, not this slice.

No third-party reasoning MCP servers are adopted in this slice. The engines are our own scripting
plus Z3. (Gemini's suggested repos — `tenth-man-mcp`, `perspective-mcp`, `decisionmatrix-mcp`,
etc. — are treated as unverified and are not dependencies; any future adoption is verified
case-by-case first.)

---

## 11. Success criteria (slice is "done")

1. `/reason-compare formal-logic "<problem>"` runs the `local` and `subagent` lanes, records both,
   and prints a comparison showing agreement or divergence, with Z3 labeled as the oracle.
2. Z3 `local` lane reproduces every §9.1 known-answer verdict.
3. A subagent-vs-Z3 **agreement rate** is produced over the known-answer set.
4. `/reason-compare graph-of-thought "<problem>"` runs the `local` and `subagent` lanes and reports
   structural agreement, with all outputs recorded as `asserted` (no false "measured" claim).
5. Missing `REASONING_SERVICES_TOKEN` degrades the `remote` lane to `unavailable` without aborting.
6. Everything is a self-contained, movable `reasoning-toolkit/` plugin directory.

---

## 12. Phasing beyond the slice

- **P2**: `devils-advocate`, rebuilt via subagents; evaluated against the Trace Ledger's **pruned
  branches as a labeled test set** ("known failures it should have predicted").
- **P3**: remaining denied engines (`decision-matrix`, `context-switcher`, `hindsight`,
  `structured-reflection`).
- **P4**: `reasoning-guide` router + `reasoning-chain` orchestrator — once engines have earned routing.
- **P5**: trace-ledger vector RAG / "ledger pointer" observability layer (`sqlite-vec`).

---

## 13. Open questions / assumptions

- **A1 (remote endpoint)**: reasoning.services URL + auth needed only for the `remote` lane; slice
  is testable without it. *Need from GT when wiring remote.*
- **A2 (the 5 you have)**: assumed accessible = `graph-of-thought`, `formal-logic`,
  `sequential-thinking`, `free-will`, `iterative-refinement`; denied = the other five. Only the
  first two matter this slice. *Correct if wrong.*
- **A3 (problem-parse determinism)**: natural-language → `{premises, conclusion}` parsing is itself
  a reasoning step; the parse is pinned per problem so all lanes judge the same encoding. The parse
  is Asserted; only the Z3 verdict on that encoding is Measured — the same boundary the Trace
  Ledger draws ("the solver checks the inference, never the encoding").

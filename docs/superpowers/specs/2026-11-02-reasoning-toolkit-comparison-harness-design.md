# Reasoning Toolkit — Comparison-Harness Vertical Slice

> **Status**: Design (approved for spec review) — **Revision 2 (post adversarial audit)**
> **Date**: 2026-11-02
> **Author**: GosuTheory (GT), with Claude Code
> **Scope**: Phase 1 vertical slice of a larger `reasoning-toolkit` Claude Code plugin

---

## 0. Revision history

**Rev 2 (2026-11-02)** — hardened after an independent adversarial audit. The architecture is
unchanged; the changes close the gaps where the experiment could have produced impressive numbers
that constrain nothing (the exact "dancing with robots" failure this toolkit exists to prevent).

| # | Change | Driven by |
| --- | --- | --- |
| C1 | The `subagent` lane is dispatched as a **plugin-defined agent with a locked, empty/Read-only toolset** — no Bash, no `mcp__*`, no web. A sentence in a prompt is not a control; a subagent inherits tools (incl. the plugin's own Z3 server) by default. | Blocker |
| C2 | `fol_prove` gains an **`unknown`** verdict (Z3 is not a decision procedure for FOL). Headline metric anchored on the **propositional** path, where Z3 is complete. | Blocker |
| C3 | **Oracle-validation set and subagent-benchmark set are separated.** The benchmark is purpose-built to discriminate a weak reasoner; the metric reports N, a confidence interval, and coverage, and is described honestly as *inference accuracy given a fixed formalization*. | Should-fix |
| C4 | graph-of-thought contrast **reframed** from ill-defined "structural agreement" to **rule-adherence replay** (a real deterministic oracle it already had). | Should-fix |
| C5 | The harness scorekeeping (register → record → compare → render) moves into a **deterministic `harness.py`**; the critic writes JSON to a file the script reads/validates/hashes. Only the dispatch stays agent-mediated. | Should-fix |
| C6 | `entails` guards against **inconsistent premises** (vacuous truth) with a distinct verdict. | Nice-to-have |
| C7 | Work sequenced: **formal-logic complete (propositional-first) is the hard gate**; reframed GoT is a stretch. | Should-fix |

---

## 1. Purpose and motivation

### 1.1 What we are building
A standalone, movable Claude Code plugin, `reasoning-toolkit`, that re-implements the
reasoning.services engines so each engine can run through interchangeable **lanes**:

- `remote` — the hosted reasoning.services MCP endpoint (for engines we have trial access to),
- `local` — a small, deterministic, open-source rebuild we write ourselves,
- `subagent` — an LLM rebuild driven by a locked-down Claude Code subagent.

The plugin's spine is a **comparison harness** that runs multiple lanes of the same engine on
the same input, records every lane's output to a results ledger, and reports where the lanes
agree, where they diverge, and — where an oracle lane exists — which lanes were wrong.

### 1.2 Why (the epistemic requirement)
The driving requirement is **"not dancing with robots."** The toolkit must produce claims that
can be checked against something that is *not* an LLM's opinion. This is the same discipline as
GT's Trace Ledger: *"put every formal move to a solver so the parts that aren't my judgment can
be checked without taking my word for any of it,"* and the Measured-vs-Asserted split that runs
down that document.

Concretely, success is a **defensible number**: for an engine with a deterministic oracle
(propositional formal logic → Z3), the per-lane **inference accuracy vs the oracle** across a
purpose-built benchmark, reported with its N, a confidence interval, and coverage. That number
quantifies how far an LLM lane can be trusted on inference *given a fixed formalization*. Where
no oracle exists (graph-of-thought scoring), the harness must say so explicitly and record those
outputs as `asserted`, never dressing them up as measured.

### 1.3 Non-goals (this slice)
- No router (`reasoning-guide`) or orchestrator (`reasoning-chain`).
- No denied engines yet (`devils-advocate`, `decision-matrix`, `context-switcher`,
  `hindsight`, `structured-reflection`).
- No trace-ledger vector RAG / "ledger pointer" observability layer.
- No Ollama or external-API critic lanes — the chosen critic is a Claude Code subagent.
- Not a portfolio feature; it merely lives in this repo's branch until lifted into its own repo.

---

## 2. Engines in scope

Only the two engines GT's Trace Ledger actually exercises ("the ones we know work"):

| Engine | Operations | Oracle | Role in slice |
| --- | --- | --- | --- |
| `formal-logic` | `entails`, `check_consistency`, `fol_prove` | **Yes.** Local Z3 — **complete for the propositional path** (always sat/unsat); the FOL path (`fol_prove`) may return `unknown` and is a caveated secondary signal. | Keystone. The propositional oracle makes the comparison objective: when the locked subagent lane disagrees with Z3, the LLM got caught. |
| `graph-of-thought` | `seed`, `generate`, `score`, `aggregate`, `refine` | **For reasoning content: none** (scores are GT's/LLM judgment, `asserted`). **For rule-adherence: yes** — the state-machine semantics are deterministic. | Contrast engine. Measures whether the subagent, maintaining the graph in-context, **correctly enforces the rules it was told to** (rule-adherence replay), while all scores/syntheses stay `asserted`. |

---

## 3. Architecture

### 3.1 Component inventory
Each component has one clear purpose, a defined interface, and explicit dependencies.

1. **Local MCP server: `formal_logic`** (Python + `z3-solver`)
   - *Does*: evaluates `entails`/`check_consistency` (propositional SAT refutation over Boolean
     consts — complete) and `fol_prove` (quantified, via Z3, with a timeout) and returns a
     structured verdict.
   - *Interface*: MCP tools `entails(premises, conclusion)`, `check_consistency(formulas)`,
     `fol_prove(premises, conclusion)`; each returns `{verdict, detail, model?/counterexample?}`.
   - *Depends on*: `z3-solver`, `mcp`. No network, no LLM, no state.

2. **Local MCP server: `graph_of_thought`** (Python + sqlite)
   - *Does*: holds a reasoning graph server-side and enforces the documented semantics —
     `score < 0.3` prunes a node permanently; `refine` is refused once a node has been merged
     (`aggregate`); `refine` returns a *new* node id. **Also serves as the replay oracle** for the
     GoT rule-adherence check (§5.3).
   - *Interface*: MCP tools `seed`, `generate`, `score`, `aggregate`, `refine`, plus
     `replay(ops[])` → returns the graph state those ops *actually* produce under the rules.
   - *Depends on*: `mcp`, stdlib `sqlite3`. No network, no LLM.

3. **Local MCP server: `ledger`** (Python + sqlite)
   - *Does*: append-only store of lane runs; computes agreement, oracle-labeled correctness, and
     coverage.
   - *Interface*: MCP tools `record_run(...)`, `compare(problem_id)`,
     `metrics(engine, lane, set_id)` (accuracy + CI + coverage), `register_problem(...)`, `query(...)`.
   - *Depends on*: `mcp`, stdlib `sqlite3`.

4. **Deterministic harness: `scripts/harness.py`** (plain Python, no LLM)
   - *Does*: everything in the comparison flow except the subagent dispatch — register the problem,
     read + validate + hash each lane's output file, call `record_run`, call `compare`/`metrics`,
     render the report. The scorekeeper is code, not an agent.
   - *Interface*: CLI `harness.py <engine> <problem_file> <lane_output_dir>`.
   - *Depends on*: stdlib + the three servers (via their sqlite files or a thin client).

5. **Agent: `agents/formal-logic-critic.md`** — the locked `subagent` lane for formal-logic.
   - *Does*: receives `{premises, conclusion}`, decides entailment **by reasoning only**, writes
     `{verdict, reasoning}` JSON to its output file.
   - *Toolset*: **empty / Read-only** — frontmatter `tools:` grants nothing that can compute or
     fetch an answer: no Bash, no Write/Edit beyond its output file, no WebFetch/WebSearch, and
     **no `mcp__*` tools** (crucially not `formal_logic`). It cannot cheat because it has no tool
     to cheat with.

6. **Agent: `agents/graph-of-thought-critic.md`** — the locked `subagent` lane for GoT.
   - *Does*: maintains a reasoning graph in-context per the rules, and emits its **operation trace**
     (the ordered `seed/generate/score/aggregate/refine` calls it believes it made) plus its claimed
     final graph, as JSON. Same locked toolset.

7. **Skills**: `comparison-harness/SKILL.md` (the thin agent-side contract: parse → dispatch critic →
   invoke `harness.py`), `formal-logic/SKILL.md` (NL→`{premises,conclusion}` parsing + lane routing),
   `graph-of-thought/SKILL.md` (the GoT protocol + lane routing).

8. **Command**: `/reason-compare <engine> <problem>` → invokes the comparison-harness skill.

9. **Config**: `config/reasoning-config.json` — per-engine lane list, oracle designation, remote gate.

10. **Plugin manifest + `.mcp.json`** — registers the three local stdio servers and the remote
    reasoning.services HTTP server; `agents/`, `skills/`, `commands/` auto-discovered from plugin root.

### 3.2 Why the subagent lane is orchestrated from a skill, not a server (validated premise)
A Claude Code MCP server process cannot call the Task/subagent tool — MCP servers expose tools *to*
the agent and hold no handle on the agent's own tools (the only server→model path is MCP "sampling,"
a single completion, not a tool-enabled isolated subagent). Therefore the LLM (`subagent`) lane is
driven by the **skill** on the main agent, which dispatches a fresh, locked critic agent per problem
and then hands its output file to `harness.py`. The servers stay deterministic; all LLM behavior is in
the critic agent; all scorekeeping is in code.

### 3.3 Proposed directory layout (built at implementation time, not now)
```
reasoning-toolkit/
├── .claude-plugin/plugin.json
├── .mcp.json
├── config/reasoning-config.json
├── commands/reason-compare.md
├── agents/
│   ├── formal-logic-critic.md        # locked, empty toolset
│   └── graph-of-thought-critic.md    # locked, empty toolset
├── skills/
│   ├── comparison-harness/SKILL.md
│   ├── formal-logic/SKILL.md
│   └── graph-of-thought/SKILL.md
├── servers/reasoning_servers/
│   ├── __init__.py
│   ├── formal_logic.py
│   ├── graph_of_thought.py
│   ├── ledger.py
│   ├── _z3_encode.py
│   └── pyproject.toml
├── scripts/
│   ├── harness.py                    # deterministic scorekeeper
│   └── seed_examples.py
├── benchmarks/
│   ├── oracle_validation.jsonl       # reproduce GT's recorded verdicts
│   └── subagent_propositional.jsonl  # purpose-built discriminating set
├── runs/                             # per-run lane output files (critic writes here)
├── tests/
│   ├── test_formal_logic.py
│   ├── test_graph_of_thought.py
│   ├── test_ledger.py
│   ├── test_critic_toolset.py        # asserts the critic agent has no cheat tools
│   └── test_harness.py
└── README.md
```
One Python package, one virtual environment, one install step.

---

## 4. Lane contract and the hybrid toggle

### 4.1 Operation contract (stable across lanes)
Every lane of an engine accepts the same operation inputs and returns a comparable result. For
`formal-logic.entails`:

- **Input**: `{ premises: string[], conclusion: string }` in the reasoning.services/Z3 surface
  syntax (operators `->`, `&`, `|`, `~`, `forall`, predicates `Name(x)`).
- **Output**: `{ verdict, reasoning, counterexample? }`.

Verdict domains (also the ledger CHECK domain, minus the lane-status values):
- `entails` ∈ `{ entails, does_not_entail, inconsistent_premises, error }`
- `check_consistency` ∈ `{ consistent, inconsistent, error }` (+ `model?` when consistent)
- `fol_prove` ∈ `{ provable, refuted, unknown, error }`
- lane-status (any op, any lane): `unavailable`, `unparseable`

`inconsistent_premises` and `unknown` are first-class outcomes, not errors (§8).

### 4.2 `reasoning-config.json`
```json
{
  "formal-logic": {
    "lanes": ["local", "subagent", "remote"],
    "oracle": "local",
    "subagent": { "agent": "formal-logic-critic" },
    "remote": { "enabled_when": "token", "server": "reasoning_remote",
                "url_env": "REASONING_SERVICES_URL", "token_env": "REASONING_SERVICES_TOKEN" }
  },
  "graph-of-thought": {
    "lanes": ["local", "subagent", "remote"],
    "oracle": null,
    "rule_adherence_oracle": "local",
    "subagent": { "agent": "graph-of-thought-critic" },
    "remote": { "enabled_when": "token", "server": "reasoning_remote" }
  }
}
```

### 4.3 Lane selection + the subagent isolation contract
- **Compare mode** (`/reason-compare`): run every available lane in `lanes[]`.
- **Single-call `auto`**: prefer `oracle` → else `local` → else `remote` (if token) → else `subagent`.
- A lane that is unavailable (no token, server down, trial lapsed) is **skipped**, recorded as
  `verdict=unavailable`, and never aborts the run. (Matches the documented 2026-09-24 trial lapse.)
- **Subagent isolation contract (C1)**: the `subagent` lane is *only* ever dispatched as the
  engine's named critic agent, which ships with a locked, empty/Read-only toolset. The critic has
  no Bash, no file write except its own output file, no web, and **no `mcp__*` tools** — so it
  physically cannot call the oracle or any solver. `test_critic_toolset.py` asserts this; if the
  critic can reach a tool that computes the answer, the whole agreement number is void.

---

## 5. Data flow

### 5.1 `/reason-compare formal-logic "<problem>"`
1. **Parse** — the `formal-logic` skill turns the problem into `{premises, conclusion}` and writes
   it to a problem file. The parse is **Asserted** (it is itself a reasoning step; see A3). All lanes
   judge this one fixed encoding, so the metric isolates *inference*, not formalization.
2. **Run each enabled lane** (skill-mediated only for the dispatch):
   - `local` / `remote` → MCP tool call; result written to `runs/<id>/<lane>.json`.
   - `subagent` → dispatch the **locked** `formal-logic-critic` agent; it writes
     `runs/<id>/subagent.json` itself.
3. **`harness.py`** (deterministic): register problem → read/validate/hash each `runs/<id>/<lane>.json`
   → `ledger.record_run(...)` with `kind` = `measured` for `local` (propositional) Z3, else `asserted`
   → `ledger.compare` / `ledger.metrics` → render the report.
4. **Compare** — if the engine has an `oracle` and the oracle returned a **definite** verdict, each
   non-oracle lane is labeled `correct`/`incorrect`. When the oracle returns `unknown` (FOL only),
   that problem is excluded from accuracy and **counted in a reported `oracle_unknown` tally** — the
   oracle shrugged; it is not silently dropped.

### 5.2 The metric (rewritten honestly — C2, C3)
- **Primary**: `inference_accuracy(lane)` over the **propositional** benchmark set (complete oracle)
  = among problems the lane answered with a parseable verdict, the fraction matching Z3. Reported
  **with N and a Wilson confidence interval** — never a bare fraction over a handful of items.
- **Coverage**: `coverage(lane)` = fraction of the set the lane answered cleanly (not
  `unparseable`/`error`). Reported *next to* accuracy, because high accuracy on low coverage means
  the lane dodged the hard ones — the selection bias is made visible, not hidden. A combined
  "answered-correctly-out-of-all" figure is reported too (unparseable counted as wrong).
- **What it means**: *inference accuracy on a fixed formalization* — **not** end-to-end logical
  trust. The parse is shared and Asserted; the Pendulum case (§6) is itself proof that the encoding,
  not the inference, is often where the judgment lives.
- **FOL (secondary, caveated)**: same computation on `fol_prove` cases, with oracle-`unknown`
  excluded from the denominator and the exclusion count reported alongside.
- Every `subagent` run records the **model id + version**; the number is model-version-specific and
  will drift.

### 5.3 `/reason-compare graph-of-thought "<problem>"` (reframed — C4)
There is no deterministic *content* oracle for GoT (even the `local` lane's scores come from an LLM),
so the slice does **not** claim "structural agreement of reasoning." Instead it measures
**rule-adherence**, which *does* have a deterministic oracle:
1. The `graph-of-thought-critic` maintains the graph in-context and emits its **operation trace** +
   its claimed final graph.
2. `harness.py` replays that trace through the `graph_of_thought` server's `replay(ops)`.
3. **Measured**: does the critic's self-reported result match what the rules actually produce — did
   it prune exactly the nodes with `score < 0.3`, correctly refuse `refine` after `aggregate`, and
   treat `refine` as producing a new id? Report adherence as a rate.
4. **Asserted** (never scored for correctness): the thought content, the scores, the synthesis text.

### 5.4 Ledger schema (sqlite)
```sql
CREATE TABLE problems (
  problem_id TEXT PRIMARY KEY,
  engine     TEXT NOT NULL,
  set_id     TEXT,                    -- 'oracle_validation' | 'subagent_propositional' | 'user'
  raw        TEXT NOT NULL,
  parsed_json TEXT,
  source     TEXT                     -- e.g. 'trace-ledger:pendulum'
);

CREATE TABLE runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT NOT NULL,
  problem_id  TEXT NOT NULL REFERENCES problems(problem_id),
  engine      TEXT NOT NULL,
  lane        TEXT NOT NULL,          -- local | subagent | remote
  op          TEXT NOT NULL,
  input_hash  TEXT NOT NULL,
  output_hash TEXT,                   -- hash of the lane's output file (tamper-evidence)
  verdict     TEXT NOT NULL,          -- domain per §4.1 incl. unavailable/unparseable
  reasoning   TEXT,
  latency_ms  INTEGER,
  model_id    TEXT,                   -- subagent lane: which model/version produced it
  kind        TEXT NOT NULL CHECK (kind IN ('measured','asserted')),
  oracle      INTEGER NOT NULL DEFAULT 0
);
```

---

## 6. Subagent (critic) prompts (sketch)

**formal-logic-critic** (locked toolset; reasons only):
> You are a logic engine. Given premises and a conclusion, decide whether the premises **entail**
> the conclusion. Reason step by step. You have no tools; do not claim to have run one. Write only
> JSON to your output file: `{"verdict": "entails"|"does_not_entail", "reasoning": "<short>"}`.

**graph-of-thought-critic** (locked toolset):
> Maintain a reasoning graph for the problem using seed/generate/score/aggregate/refine. Enforce:
> a node scored below 0.3 is pruned; a node cannot be refined after it is aggregated; refine creates
> a new node id. Emit JSON: `{"ops": [...ordered calls...], "final_graph": {...}}`.

The locked toolset — not the prose — is what guarantees "no solver." The prose only shapes output.

---

## 7. Remote lane wiring

`.mcp.json` registers reasoning.services as an HTTP MCP server with
`Authorization: Bearer ${REASONING_SERVICES_TOKEN}` and base URL `${REASONING_SERVICES_URL}`.
Tool names observed in the Trace Ledger: `seed/generate/score/aggregate/refine` and
`entails/check_consistency/fol_prove`.

**Assumption / open item (A1)**: the exact endpoint URL and auth are not in the ledger. The `local`
and `subagent` lanes need none of this, so the slice is fully buildable and testable without it.
The remote lane is wired last; until then it records `unavailable` and the harness proceeds.

---

## 8. Error handling and logical footguns

- **Z3 propositional parse/syntax error** → structured `❌ Invalid Input` result, `verdict=error`.
  Regression test includes the HTML-escaped-ampersand case (`&amp;` vs `&`) from Trace Ledger §5.
- **Inconsistent premises (C6)** → before reporting `entails`, check that the premises alone are
  SAT. If they are UNSAT, every conclusion is vacuously entailed, so return
  `verdict=inconsistent_premises`, never a clean `entails`. Regression test with contradictory
  premises.
- **Vacuous `consistent`** → `check_consistency` flags when the only satisfying model sets every
  atom false (the Part III footgun) rather than reporting a clean pass.
- **FOL `unknown` (C2)** → Z3 is not a decision procedure for quantified logic; set an explicit
  timeout and map timeout/incompleteness → `verdict=unknown`. The oracle is allowed to have no
  answer, and the metric excludes and counts those.
- **Subagent returns non-JSON / empty file** → `verdict=unparseable`; counted against coverage.
- **Remote refuses / token lapsed** → `verdict=unavailable`, run continues.
- **Ledger** is append-only; `input_hash` + `output_hash` identify re-runs and make tampering evident.

---

## 9. Testing strategy — the proof the toolkit constrains something

### 9.1 Oracle validation set (`benchmarks/oracle_validation.jsonl`)
Purpose: prove the `local` Z3 lane reproduces GT's recorded verdicts (Measured ground truth from the
Trace Ledger). **Not** used to score the subagent.
- **Pendulum (§5)**: propositional → `does_not_entail` + counterexample; FOL → `provable`.
- **054 meta-theorem**: `provable` quantified; `~thing_ontology`, `fact -> ~truth` → `entails`.
- **040 T14**: both derivations → `entails`, no counterexample.
If Z3 matches these, the oracle is trustworthy. (These verdicts are GT's own; the Trace Ledger is the
source of record.)

### 9.2 Subagent benchmark set (`benchmarks/subagent_propositional.jsonl`) — C3
Purpose: measure the subagent lane against Z3. **Propositional only** (complete oracle), and
**purpose-built to discriminate a weak reasoner**: long modus-tollens chains, XOR/parity, pigeonhole,
nested implication, material-implication and vacuous-truth traps, plus easy controls. Minimum N stated
(target ≥ 40 so a Wilson CI is meaningful); every item has a Z3-computed gold verdict. The agreement
figure is reported with N, CI, and coverage (§5.2).

### 9.3 Anti-cheat test (`test_critic_toolset.py`) — C1
Assert the critic agent's resolved tool surface contains nothing that can compute or fetch a verdict
(no Bash, no `mcp__*`, no web). A belt-and-braces behavioral check: hand the critic a problem that a
tool would trivially solve and confirm no tool call occurs. If this fails, the agreement number is
void.

### 9.4 graph-of-thought rule-adherence (`test_graph_of_thought.py`) — C4
- Server semantics: `score 0.15` → pruned + flagged; `refine` after `aggregate` → refused; `refine`
  otherwise → new id; `aggregate(a,b,c)` → one merged node.
- `replay(ops)` is deterministic and matches direct calls.
- Adherence scoring: a known-good trace scores 1.0; an injected rule violation (e.g. a refine after
  aggregate the critic *claims* succeeded) is detected and lowers the score.

### 9.5 Harness + ledger (`test_harness.py`, `test_ledger.py`)
- A multi-lane run writes one `runs` row per lane with correct `kind`, `output_hash`, `model_id`.
- `metrics` math is correct on a hand-checked fixture: accuracy, Wilson CI, coverage, `oracle_unknown`
  tally, inconsistent-premises handling.

All tests run locally: no token, no paid API. Only the subagent-lane tests need a session.

---

## 10. Dependencies

- `z3-solver` (PyPI) — the official Microsoft Z3 build (not the unrelated `z3` package). Version
  pinned and import-verified at implementation.
- `mcp` (Python MCP SDK) — server framework. Version pinned at implementation.
- stdlib `sqlite3` — graph + ledger storage.
- `sqlite-vec` — **deferred to the hindsight/RAG phase**, not this slice.

No third-party reasoning MCP servers are adopted. The engines are our own scripting plus Z3.
(Gemini's suggested repos — `tenth-man-mcp`, `perspective-mcp`, `decisionmatrix-mcp`, etc. — are
unverified and not dependencies; any future adoption is verified case-by-case first.)

---

## 11. Success criteria

**Hard gate (formal-logic complete, propositional-first) — C7:**
1. `/reason-compare formal-logic "<problem>"` runs `local` + `subagent` lanes, records both (with
   `output_hash`, `model_id`), and prints a comparison with Z3 labeled as oracle.
2. Z3 `local` lane reproduces every §9.1 oracle-validation verdict; `inconsistent_premises` and
   propositional completeness behave per §8.
3. A subagent-vs-Z3 **inference-accuracy** figure is produced over the §9.2 discriminating benchmark,
   reported with **N, Wilson CI, and coverage**, with the subagent dispatched via the **locked**
   critic agent (proven tool-less by §9.3). No figure is accepted from an unlocked subagent.

**Soft gate (stretch):**
4. `/reason-compare graph-of-thought "<problem>"` runs `local` + `subagent` and reports a
   **rule-adherence** rate via `replay` (Measured), with all scores/syntheses recorded `asserted`.

**Both gates:**
5. Missing `REASONING_SERVICES_TOKEN` degrades the `remote` lane to `unavailable` without aborting.
6. Everything is a self-contained, movable `reasoning-toolkit/` plugin directory; scorekeeping is in
   `harness.py` (code), not an agent.

---

## 12. Phasing beyond the slice

- **P2**: `devils-advocate`, rebuilt via a locked subagent; evaluated against the Trace Ledger's
  **pruned branches as a labeled test set** ("known failures it should have predicted").
- **P3**: remaining denied engines (`decision-matrix`, `context-switcher`, `hindsight`,
  `structured-reflection`).
- **P4**: `reasoning-guide` router + `reasoning-chain` orchestrator — once engines have earned routing.
- **P5**: trace-ledger vector RAG / "ledger pointer" observability layer (`sqlite-vec`).

---

## 13. Open questions / assumptions

- **A1 (remote endpoint)**: reasoning.services URL + auth needed only for the `remote` lane; slice is
  testable without it. *Need from GT when wiring remote.*
- **A2 (the 5 you have)**: assumed accessible = `graph-of-thought`, `formal-logic`,
  `sequential-thinking`, `free-will`, `iterative-refinement`; denied = the other five. Only the first
  two matter this slice. *Correct if wrong.*
- **A3 (parse boundary)**: NL → `{premises, conclusion}` parsing is a reasoning step; the parse is
  pinned per problem and marked `asserted`. Only Z3's verdict on that fixed encoding is `measured`.
  The metric therefore measures *inference given a formalization*, not end-to-end trust — the same
  boundary the Trace Ledger draws ("the solver checks the inference, never the encoding").
- **A4 (model drift)**: the subagent agreement number is specific to the model id/version recorded on
  each run; re-baseline when the model changes.

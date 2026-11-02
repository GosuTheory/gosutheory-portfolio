# Reasoning Toolkit — Comparison-Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a standalone Claude Code plugin that runs the `formal-logic` and `graph-of-thought` engines across interchangeable lanes and reports, with a defensible number, how far the LLM lane can be trusted against a deterministic oracle.

**Architecture:** Deterministic MCP servers (Z3 logic, GoT graph store, results ledger) hold all compute and state; a tool-locked critic **agent** is the LLM lane (it cannot reach a solver or the gold answers); a plain-Python `harness.py` is the scorekeeper. Skills only parse the problem and dispatch the critic. Lanes are selected per-engine from a config file.

**Tech Stack:** Python 3.11+, `z3-solver`, `mcp` (Python SDK, FastMCP), stdlib `sqlite3`, pytest. Claude Code plugin packaging (`.claude-plugin/plugin.json`, `.mcp.json`, `agents/`, `skills/`, `commands/`).

**Spec:** `docs/superpowers/specs/2026-11-02-reasoning-toolkit-comparison-harness-design.md` (read it alongside this plan; the plan argues from it).

## Global Constraints

- **Package root:** everything lives in a self-contained, movable `reasoning-toolkit/` directory (spec §1.3, §3.3).
- **Dependencies:** `z3-solver` (the official Microsoft build — NOT the unrelated `z3` package), `mcp`, pytest. Pin exact versions in `pyproject.toml` and import-verify at build. `sqlite-vec` is OUT of scope.
- **Verdict domains (exact):** `entails ∈ {entails, does_not_entail, inconsistent_premises, error}`; `check_consistency ∈ {consistent, inconsistent, error}`; `fol_prove ∈ {provable, refuted, unknown, error}`; lane-status (any op) `∈ {unavailable, unparseable}`.
- **Measured vs Asserted:** `kind ∈ {measured, asserted}`. ONLY the propositional Z3 lane (`entails`/`check_consistency` via `local`) is `measured`. Every `subagent` run, every `remote` run, every `fol_prove` result, and all graph-of-thought content is `asserted`.
- **Critic isolation:** the `subagent` lane is dispatched ONLY as the engine's named critic agent, whose frontmatter denies Bash, Read, Write-outside-its-output, WebFetch, WebSearch, Task, and all `mcp__*`. The gold verdict is taken from the live `local` Z3 lane in the same run, never a file the critic could read. The number is void if `test_critic_toolset` fails.
- **Scorekeeping is code:** register → record → compare → render runs in `harness.py`, never in an agent's prose.
- **Ledger:** append-only; every row carries `input_hash` and `output_hash` (tamper-evidence); `subagent` rows carry `model_id`.
- **Metric honesty:** the headline is **propositional inference accuracy given a fixed formalization**, reported with N, a Wilson 95% CI, and coverage. FOL agreement is secondary and excludes (and counts) oracle-`unknown` problems.
- **Plugin paths:** `.mcp.json` uses `${CLAUDE_PLUGIN_ROOT}`; servers are reachable as `mcp__plugin_reasoning-toolkit_<server>__<tool>`.
- **Commits:** Conventional Commits (`feat:`/`test:`/`docs:` …) per the repo CLAUDE.md, plus the session's `Co-Authored-By` / `Claude-Session` trailers.

## Review Focus

Input classes the spec implies but that no happy-path task would otherwise exercise — each pinned to the task that owns it:

1. **Malformed / adversarial logic text** (unbalanced parens, unknown token, the HTML-escaped `&amp;` from spec §5/§8) → structured `error`, never a crash or a stack trace. → Task 2/3.
2. **Inconsistent premises** (premises UNSAT on their own) → `inconsistent_premises`, never a vacuous `entails`. → Task 3.
3. **Z3 returns `unknown` on FOL** (undecidable fragment / timeout) → `unknown`, excluded from accuracy and counted, never a crash or a silent drop. → Task 4.
4. **A critic with a cheat path** (a tool that computes or reads the answer) → prevented by the agent lockdown and caught by a test; if uncaught, the metric is void. → Task 7.
5. **Low coverage / dodged problems** (critic returns `unparseable` or errors on the hard ones) → coverage reported next to accuracy and `unparseable` counted as wrong, so accuracy cannot be inflated by selection. → Task 5.

---

## File structure

```
reasoning-toolkit/
├── .claude-plugin/plugin.json
├── .mcp.json
├── config/reasoning-config.json
├── commands/reason-compare.md
├── agents/{formal-logic-critic.md, graph-of-thought-critic.md}
├── skills/{comparison-harness,formal-logic,graph-of-thought}/SKILL.md
├── servers/reasoning_servers/{__init__.py, _z3_encode.py, formal_logic.py,
│                              graph_of_thought.py, ledger.py, pyproject.toml}
├── scripts/{harness.py, seed_examples.py}
├── benchmarks/{oracle_validation.jsonl, subagent_propositional.jsonl}
├── runs/                       # critic output files (gitignored)
├── tests/{test_z3_encode.py, test_formal_logic.py, test_fol.py, test_ledger.py,
│          test_harness.py, test_critic_toolset.py, test_graph_of_thought.py}
└── README.md
```

Hard gate = Tasks 1–8 (`formal-logic` complete). Stretch = Tasks 9–10 (`graph-of-thought`).

---

### Task 1: Package scaffold, plugin manifest, config

**Files:**
- Create: `reasoning-toolkit/servers/reasoning_servers/__init__.py`, `.../pyproject.toml`
- Create: `reasoning-toolkit/.claude-plugin/plugin.json`, `reasoning-toolkit/.mcp.json`
- Create: `reasoning-toolkit/config/reasoning-config.json`, `reasoning-toolkit/.gitignore` (ignores `runs/`)
- Test: `reasoning-toolkit/tests/test_config.py`

**Interfaces:**
- Produces: an installable `reasoning_servers` package; `load_config(path) -> dict` in `reasoning_servers/__init__.py`; `.mcp.json` declaring stdio servers `formal_logic`, `graph_of_thought`, `ledger` (commands `python -m reasoning_servers.<name>` under `${CLAUDE_PLUGIN_ROOT}/servers`) and an HTTP `reasoning_remote` gated on `REASONING_SERVICES_URL`/`REASONING_SERVICES_TOKEN`.

- [ ] **Step 1: Write failing test** `test_config.py::test_config_lists_both_engines_with_oracle` — `load_config` returns a dict where `config["formal-logic"]["oracle"] == "local"` and `config["graph-of-thought"]["oracle"] is None` and both list lanes `["local","subagent","remote"]`; `test_mcp_json_valid` asserts `.mcp.json` parses and has the three local server keys.
- [ ] **Step 2: Run** `pytest tests/test_config.py -v` → FAIL (module/files missing).
- [ ] **Step 3: Implement** `load_config(path: str) -> dict` (thin `json.load` + schema asserts) and author `pyproject.toml` (deps: `z3-solver`, `mcp`; dev: `pytest`), `plugin.json` (`name: reasoning-toolkit`, version, description), `.mcp.json` (per spec §4.2/§7, using `${CLAUDE_PLUGIN_ROOT}`), `config/reasoning-config.json` (verbatim spec §4.2).
- [ ] **Step 4: Run** `pip install -e reasoning-toolkit/servers && pytest tests/test_config.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: scaffold reasoning-toolkit plugin, servers package, and config`.

---

### Task 2: Propositional formula parser (`_z3_encode.py`)

**Files:**
- Create: `reasoning_servers/_z3_encode.py`
- Test: `tests/test_z3_encode.py`

**Interfaces:**
- Produces: `class ParseError(Exception)` with `.message: str` and `.position: int|None`; `parse_prop(formula: str, env: dict[str, z3.BoolRef]) -> z3.BoolRef` (mutates `env`, creating a `z3.Bool` per new atom). Operators, by precedence low→high: `<->`, `->` (right-assoc), `|`, `&`, `~`, parentheses; atoms match `[A-Za-z_][A-Za-z0-9_]*`.

- [ ] **Step 1: Write failing tests** in `test_z3_encode.py`:
  - `test_parses_implication`: `parse_prop("a -> b", env)` yields a term equal to `z3.Implies(env['a'], env['b'])` (compare via `z3.eq` after parsing, or by solving equivalence).
  - `test_precedence`: `~a & b -> c` parses as `Implies(And(Not(a),b), c)`.
  - `test_rejects_html_escaped_amp`: `parse_prop("a &amp; b", env)` raises `ParseError` whose `position` points at `;` (the spec §5 case).
  - `test_rejects_unbalanced_paren`: `parse_prop("(a & b", env)` raises `ParseError`.
- [ ] **Step 2: Run** `pytest tests/test_z3_encode.py -v` → FAIL.
- [ ] **Step 3: Implement** a tokenizer + Pratt/recursive-descent parser building Z3 `BoolRef`s; raise `ParseError(message, position)` on an unexpected token, unterminated group, or trailing input. (Algorithm is the implementer's; the operator table and precedence above fix the one reasonable parse.)
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: propositional formula parser with structured parse errors`.

---

### Task 3: `formal_logic` server — propositional `entails` + `check_consistency` (the complete oracle)

**Files:**
- Create: `reasoning_servers/formal_logic.py` (entails, check_consistency, server wiring)
- Test: `tests/test_formal_logic.py`

**Interfaces:**
- Consumes: `parse_prop`, `ParseError` (Task 2).
- Produces: `entails(premises: list[str], conclusion: str) -> dict` and `check_consistency(formulas: list[str]) -> dict`, each returning `{"verdict": str, "detail": str, "counterexample": dict|None, "model": dict|None}`; both registered as FastMCP tools on a `FastMCP("formal_logic")` server with a `main()` stdio entrypoint (`python -m reasoning_servers.formal_logic`).

- [ ] **Step 1: Write failing tests**:
  - `test_entails_true`: `entails(["a","a -> b"], "b")["verdict"] == "entails"`.
  - `test_pendulum_propositional_does_not_entail`: the spec §9.1 propositional pendulum encoding returns `does_not_entail` with a non-empty `counterexample` (one satisfying assignment of `premises ∧ ¬conclusion`).
  - `test_inconsistent_premises`: `entails(["a","~a"], "b")["verdict"] == "inconsistent_premises"` (NOT `entails`).
  - `test_consistency_vacuous_all_false_flagged`: a set of pure implications returns `consistent` but `detail` notes the model is all-false (spec §8).
  - `test_syntax_error_verdict`: a premise `"a &amp; b"` yields `{"verdict":"error"}` carrying the parser position, not an exception.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `entails`: parse all premises + conclusion; **first** check `Solver().add(*premises); if unsat → inconsistent_premises`; else add `Not(conclusion)`; `unsat → entails`, `sat → does_not_entail` with the model serialized to `counterexample`. `check_consistency`: `sat → consistent` (+ serialized `model`, flag if every atom is False), `unsat → inconsistent`. Wrap `ParseError → {"verdict":"error", "detail":..., "position":...}`. Register both as `@mcp.tool()`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: propositional entails/check_consistency with inconsistent-premises guard`.

---

### Task 4: `formal_logic` server — `fol_prove` (FOL, caveated, with `unknown`)

**Files:**
- Modify: `reasoning_servers/formal_logic.py` (add `fol_prove` + a small FOL encoder, or extend `_z3_encode.py`)
- Test: `tests/test_fol.py`

**Interfaces:**
- Produces: `fol_prove(premises: list[str], conclusion: str, timeout_ms: int = 5000) -> dict` returning `{"verdict": one of provable|refuted|unknown|error, "detail": str, "countermodel": dict|None}`; FastMCP tool on the same server.

- [ ] **Step 1: Write failing tests**:
  - `test_pendulum_fol_provable`: the spec §9.1 predicate pendulum encoding (`forall A, (IsObservation(A) -> StableAbsentNewEvidence(A))` …) returns `provable`.
  - `test_054_meta_theorem_provable`: the §9.1 054 quantified statement returns `provable`.
  - `test_fol_refuted_returns_countermodel`: a knowingly invalid quantified argument returns `refuted` with a `countermodel`.
  - `test_fol_unknown_on_timeout`: a formula that forces Z3 past `timeout_ms` returns `unknown` (not `error`, not a hang).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Encode the FOL fragment the benchmarks use (`forall`, unary/binary predicates, `->`, `&`, `~`) into Z3 sorts + `z3.ForAll`; prove by checking unsat of `premises ∧ ¬conclusion` with `Solver(); s.set("timeout", timeout_ms)`; map `unsat → provable`, `sat → refuted` (+ countermodel), `unknown → unknown`. Scope: only the fragment the oracle-validation + benchmark sets need; richer FOL is a later phase.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: fol_prove via Z3 with explicit unknown verdict and timeout`.

---

### Task 5: `ledger` server (schema, record, compare, metrics)

**Files:**
- Create: `reasoning_servers/ledger.py`
- Test: `tests/test_ledger.py`

**Interfaces:**
- Produces: FastMCP tools on `FastMCP("ledger")` —
  - `register_problem(problem_id, engine, set_id, raw, parsed_json, source) -> dict`
  - `record_run(problem_id, engine, lane, op, input_hash, output_hash, verdict, reasoning, latency_ms, model_id, kind, oracle) -> dict`
  - `compare(problem_id) -> dict` (per-problem lane verdicts + oracle label where the oracle gave a definite verdict)
  - `metrics(engine, lane, set_id) -> dict` returning `{n, agreement, wilson_lo, wilson_hi, coverage, oracle_unknown, answered_correct_over_all}`.
  Schema exactly per spec §5.4; DB path from env (default under `${CLAUDE_PLUGIN_DATA}`), append-only.

- [ ] **Step 1: Write failing tests** on an in-memory/temp DB:
  - `test_record_and_compare_labels_against_oracle`: with an oracle `local` row `entails` and a `subagent` row `does_not_entail`, `compare` labels subagent `incorrect`.
  - `test_metrics_wilson_ci`: 8/10 agreements → `agreement == 0.8` and `wilson_lo/hi` match the hand-computed Wilson 95% interval (assert to 3 dp).
  - `test_coverage_counts_unparseable_as_wrong`: 5 correct, 3 wrong, 2 `unparseable` over 10 → `coverage == 0.8`, `answered_correct_over_all == 0.5`.
  - `test_oracle_unknown_excluded_and_counted`: FOL set where oracle is `unknown` on 2 of 6 → those 2 excluded from `agreement` denominator and `oracle_unknown == 2`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the schema + tools. Wilson score interval:
  ```
  # p = agreements/n_answered ; z = 1.96
  denom = 1 + z**2/n
  centre = (p + z*z/(2*n)) / denom
  half = (z/denom) * sqrt(p*(1-p)/n + z*z/(4*n*n))
  lo, hi = centre - half, centre + half
  ```
  `coverage = answered / n_total`; `answered_correct_over_all = correct / n_total`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: results ledger with compare, Wilson-CI metrics, and coverage`.

---

### Task 6: `harness.py` — deterministic scorekeeper

**Files:**
- Create: `scripts/harness.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `ledger` tools (Task 5) via a thin in-process client or direct sqlite.
- Produces: `run_comparison(engine: str, problem: dict, lane_outputs: dict[str, dict]) -> dict` (register → hash each lane output → record_run → compare → metrics → report dict) and a CLI `python scripts/harness.py <engine> <problem_file.json> <lane_output_dir>`. `kind` assigned by rule: `local`+`formal-logic` → `measured`, else `asserted`.

- [ ] **Step 1: Write failing tests** (no LLM; lane outputs are fixture files):
  - `test_harness_records_one_row_per_lane`: given `local` + `subagent` fixture outputs, two `runs` rows appear with correct `kind` and a populated `output_hash`.
  - `test_harness_report_flags_divergence`: when `subagent` disagrees with the `local` oracle, the report marks it `incorrect`.
  - `test_harness_handles_unparseable_subagent`: a non-JSON subagent output file → `verdict=unparseable`, recorded, not a crash.
  - `test_harness_tolerates_unavailable_lane`: a run with only `local`+`subagent` present (no `remote`), and separately a lane output of `{"verdict":"unavailable"}`, still completes and produces metrics from the remaining lanes — never aborts (success criterion §11 #5).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `run_comparison` + CLI; read each `lane_output_dir/<lane>.json`, `output_hash = sha256(bytes)`, validate against the verdict domain, record, compare, render a markdown table report.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: deterministic comparison harness (scorekeeper in code)`.

---

### Task 7: Locked critic agent + skills + command (the `subagent` lane)

**Files:**
- Create: `agents/formal-logic-critic.md`
- Create: `skills/comparison-harness/SKILL.md`, `skills/formal-logic/SKILL.md`
- Create: `commands/reason-compare.md`
- Test: `tests/test_critic_toolset.py`

**Interfaces:**
- Consumes: `harness.py` (Task 6), `config` (Task 1).
- Produces: the dispatch contract — the `comparison-harness` skill parses NL→`{premises,conclusion}` (recorded `asserted`), writes the problem file, dispatches `formal-logic-critic` which returns/writes `{verdict, reasoning}` JSON to `runs/<id>/subagent.json`, then invokes `harness.py`.

- [ ] **Step 1: Write failing test** `test_critic_toolset.py::test_critic_has_no_cheat_tools`: parse `agents/formal-logic-critic.md` frontmatter and assert its effective toolset excludes `Bash`, `Read`, `WebFetch`, `WebSearch`, `Task`, and any token matching `mcp__*` — via a `tools:` allowlist limited to `["Write"]` AND a `disallowedTools:` denylist naming the above (defense in depth).
- [ ] **Step 2: Run** `pytest tests/test_critic_toolset.py -v` → FAIL.
- [ ] **Step 3: Implement** `formal-logic-critic.md` with that frontmatter and the spec §6 reasoning-only body (it may ONLY write its output file); author the two skills and the `/reason-compare` command. The critic never receives a gold verdict or benchmark path — only `{premises, conclusion}`.
- [ ] **Step 4: Run** `pytest tests/test_critic_toolset.py -v` → PASS. Then a documented **manual** behavioral check (session-only): hand the critic a trivially solvable problem and confirm its transcript shows zero tool calls; record the result in the PR.
- [ ] **Step 5: Commit** `feat: tool-locked formal-logic critic, harness skills, and /reason-compare`.

---

### Task 8: Benchmarks + oracle validation

**Files:**
- Create: `scripts/seed_examples.py`, `benchmarks/oracle_validation.jsonl`, `benchmarks/subagent_propositional.jsonl`
- Test: `tests/test_benchmarks.py`

**Interfaces:**
- Consumes: `formal_logic.entails`/`fol_prove` (Tasks 3–4).
- Produces: `oracle_validation.jsonl` (pendulum, 054, 040 — each `{raw, premises, conclusion, op, gold}` with GT's recorded verdict as `gold`); `subagent_propositional.jsonl` (≥ 40 purpose-built propositional items with Z3-computed `gold`).

- [ ] **Step 1: Write failing tests**:
  - `test_z3_reproduces_oracle_validation`: for every row in `oracle_validation.jsonl`, the matching `formal_logic` op returns `verdict == gold` (ties spec §9.1 — the oracle is trustworthy).
  - `test_benchmark_gold_selfconsistent`: for every `subagent_propositional.jsonl` row, Z3 recomputes the stored `gold` (the gold is really Z3's).
  - `test_benchmark_min_size_and_variety`: ≥ 40 rows, and both `entails`/`does_not_entail` are represented, plus at least one each of: long modus-tollens chain, parity/XOR, pigeonhole, nested implication, vacuous-truth trap.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the two datasets (hand-author the discriminating items; `seed_examples.py` computes/validates gold via the `formal_logic` functions and can load them into the ledger with `set_id`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: oracle-validation and discriminating subagent benchmark sets`.

> **Hard gate complete.** At this point success criteria §11 #1–#3, #5, #6 are met: `/reason-compare formal-logic` runs local+subagent, Z3 reproduces the ledger verdicts, and a subagent-vs-Z3 accuracy with N/CI/coverage is produced from a tool-locked critic.

---

### Task 9: `graph_of_thought` server + `replay` (stretch)

**Files:**
- Create: `reasoning_servers/graph_of_thought.py`
- Test: `tests/test_graph_of_thought.py`

**Interfaces:**
- Produces: FastMCP tools `seed`, `generate`, `score`, `aggregate`, `refine`, and `replay(ops: list[dict]) -> dict` (applies an op sequence under the rules and returns the resulting graph state). Rules: `score < 0.3` prunes permanently; `refine` after a node is `aggregate`d is refused; `refine` returns a new node id. sqlite-backed.

- [ ] **Step 1: Write failing tests**:
  - `test_score_below_threshold_prunes`: `score(n, 0.15)` → node flagged pruned.
  - `test_refine_after_aggregate_refused`; `test_refine_returns_new_id`; `test_aggregate_merges`.
  - `test_replay_matches_direct_calls`: `replay(ops)` yields the same final state as issuing those ops directly.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the store + rule enforcement + `replay`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: graph-of-thought store with rule enforcement and replay`.

---

### Task 10: GoT critic + rule-adherence scoring (stretch)

**Files:**
- Create: `agents/graph-of-thought-critic.md`, `skills/graph-of-thought/SKILL.md`
- Modify: `scripts/harness.py` (GoT adherence path), `tests/test_harness.py`
- Test: `tests/test_critic_toolset.py` (extend), `tests/test_harness.py` (extend)

**Interfaces:**
- Consumes: `graph_of_thought.replay` (Task 9), `harness.run_comparison` (Task 6).
- Produces: `score_adherence(claimed: dict, replayed: dict) -> dict` returning `{adherence: float, violations: list}`; GoT path in harness records adherence `measured` and scores/syntheses `asserted`.

- [ ] **Step 1: Write failing tests**:
  - `test_graph_of_thought_critic_has_no_cheat_tools` (same lockdown as Task 7).
  - `test_adherence_perfect_on_valid_trace`: a rules-respecting claimed trace scores `1.0`.
  - `test_adherence_detects_violation`: a trace claiming a successful refine-after-aggregate scores `< 1.0` with that violation listed.
  - `test_got_scores_recorded_asserted`: content/scores rows have `kind == "asserted"`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the critic agent (locked toolset; emits `{ops, final_graph}`), the skill, and `score_adherence` (replay `ops`, diff claimed vs actual prune/refuse/new-id decisions).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: graph-of-thought rule-adherence lane and scoring`.

---

## Notes for the executor

- **Run servers headlessly in tests** by importing the tool functions directly (don't require a live MCP transport for unit tests); reserve end-to-end MCP wiring for the manual session check in Task 7 Step 4.
- **The critic manual check is the only session-dependent step.** Everything else is deterministic pytest and must pass in CI without a model, a token, or network.
- **Remote lane (A1):** unwired until GT supplies `REASONING_SERVICES_URL`/`REASONING_SERVICES_TOKEN`; it records `unavailable` and nothing depends on it.

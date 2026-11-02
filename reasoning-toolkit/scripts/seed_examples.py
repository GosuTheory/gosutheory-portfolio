"""Author the benchmark sets and stamp every gold verdict with Z3.

- oracle_validation.jsonl: real Trace-Ledger solver-log encodings; Z3 must
  reproduce the ledger's recorded verdict (the oracle is trustworthy).
- subagent_propositional.jsonl: purpose-built, propositional (so Z3 is a complete
  oracle), tagged to discriminate a weak reasoner. Gold is Z3's, verified here
  against the author's expectation.

Run: python scripts/seed_examples.py
"""
import json
from pathlib import Path

from reasoning_servers.formal_logic import check_consistency, entails, fol_prove

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"

# --- Oracle validation: exact encodings from the Trace Ledger solver log ---
ORACLE_VALIDATION = [
    {"id": "pendulum_propositional", "op": "entails",
     "raw": "Trace Ledger section 5: bare-proposition encoding of the pendulum.",
     "premises": [
         "is_observation -> stable_absent_new_evidence",
         "revised_under_prompting_alone -> ~stable_absent_new_evidence",
         "account_A_revised_under_prompting_alone",
         "account_B_revised_under_prompting_alone",
     ],
     "conclusion": "~account_A_is_observation & ~account_B_is_observation",
     "gold": "does_not_entail"},
    {"id": "identity_in_brain_chain", "op": "entails",
     "raw": "Trace Ledger dyad solver log (line 1590): identity-in-brain chain.",
     "premises": [
         "identity_in_brain -> consciousness",
         "consciousness -> dyadic_coupling",
         "dyadic_coupling -> ~property_of_single_relatum",
         "identity_in_brain -> property_of_single_relatum",
     ],
     "conclusion": "~identity_in_brain",
     "gold": "entails"},
    {"id": "pendulum_fol", "op": "fol_prove",
     "raw": "Trace Ledger dyad T9-T12: pendulum, bound per account.",
     "premises": [
         "forall A, (IsObservation(A) -> StableAbsentNewEvidence(A))",
         "forall A, (RevisedUnderPromptingAlone(A) -> ~StableAbsentNewEvidence(A))",
         "RevisedUnderPromptingAlone(account_a)",
         "RevisedUnderPromptingAlone(account_b)",
     ],
     "conclusion": "~IsObservation(account_a) & ~IsObservation(account_b)",
     "gold": "provable"},
    {"id": "meta_theorem_054", "op": "fol_prove",
     "raw": "Trace Ledger 054 T28: the meta-theorem as written.",
     "premises": ["Uses(s, fq, q0)", "~ExplicitAccept(s, fq)"],
     "conclusion": "~(forall F, forall Q, (Uses(s, F, Q) -> ExplicitAccept(s, F)))",
     "gold": "provable"},
    {"id": "dialogical_necessity", "op": "fol_prove",
     "raw": "Trace Ledger: Theorem of Dialogical Necessity.",
     "premises": [
         "forall X, (Consciousness(X) -> OmegaVaries(X))",
         "forall X, (Solipsism(X) -> ~OmegaVaries(X))",
     ],
     "conclusion": "forall X, (Solipsism(X) -> ~Consciousness(X))",
     "gold": "provable"},
    {"id": "jar_test", "op": "fol_prove",
     "raw": "Trace Ledger dyad T11: the jar test.",
     "premises": [
         "forall S, (HasVisibility(S) -> CanReport(S, jar_color))",
         "~CanReport(c, jar_color)",
     ],
     "conclusion": "~HasVisibility(c)",
     "gold": "provable"},
    {"id": "information_loss_trap", "op": "fol_prove",
     "raw": "Trace Ledger NB T3-T4: the information-loss trap.",
     "premises": [
         "forall X, (Information(X) -> Event(X))",
         "forall X, (Event(X) -> ~OnLedger(X))",
         "forall X, (CanBeNamed(X) -> OnLedger(X))",
         "CanBeNamed(what_was_lost)",
     ],
     "conclusion": "~Information(what_was_lost)",
     "gold": "provable"},
]

# --- Subagent benchmark: (id, premises, conclusion, expected, tags) ---
_S = [
    # controls
    ("mp", ["a", "a -> b"], "b", "entails", ["control"]),
    ("mt", ["a -> b", "~b"], "~a", "entails", ["control"]),
    ("disj_syllogism", ["a | b", "~a"], "b", "entails", ["control"]),
    ("hyp_syllogism", ["a -> b", "b -> c"], "a -> c", "entails", ["control"]),
    ("conjunction", ["a", "b"], "a & b", "entails", ["control"]),
    ("contrapositive", ["a -> b"], "~b -> ~a", "entails", ["control"]),
    ("affirming_consequent", ["a -> b", "b"], "a", "does_not_entail", ["control", "fallacy"]),
    ("denying_antecedent", ["a -> b", "~a"], "~b", "does_not_entail", ["control", "fallacy"]),
    # modus tollens chains
    ("mt_chain4", ["a -> b", "b -> c", "c -> d", "~d"], "~a", "entails", ["modus_tollens_chain"]),
    ("mt_chain5", ["a -> b", "b -> c", "c -> d", "d -> e", "~e"], "~a", "entails", ["modus_tollens_chain"]),
    ("mt_chain6", ["a -> b", "b -> c", "c -> d", "d -> e", "e -> f", "~f"], "~a", "entails", ["modus_tollens_chain"]),
    ("mt_chain7", ["p1 -> p2", "p2 -> p3", "p3 -> p4", "p4 -> p5", "p5 -> p6", "p6 -> p7", "~p7"], "~p1", "entails", ["modus_tollens_chain"]),
    ("mt_chain_invalid", ["a -> b", "b -> c", "c -> d", "~d"], "b", "does_not_entail", ["modus_tollens_chain"]),
    # parity / xor
    ("exactly_one_a", ["a | b | c", "~(a & b)", "~(a & c)", "~(b & c)", "a"], "~b & ~c", "entails", ["parity"]),
    ("exactly_one_c", ["a | b | c", "~(a & b)", "~(a & c)", "~(b & c)", "~a", "~b"], "c", "entails", ["parity"]),
    ("xor_chain", ["(a | b) & ~(a & b)", "(b | c) & ~(b & c)", "a"], "c", "entails", ["parity"]),
    ("xor_underdetermined", ["(a | b) & ~(a & b)"], "a", "does_not_entail", ["parity"]),
    # pigeonhole (unsatisfiable premises)
    ("pigeonhole_3_2", [
        "p1h1 | p1h2", "p2h1 | p2h2", "p3h1 | p3h2",
        "~(p1h1 & p2h1)", "~(p1h1 & p3h1)", "~(p2h1 & p3h1)",
        "~(p1h2 & p2h2)", "~(p1h2 & p3h2)", "~(p2h2 & p3h2)",
    ], "p1h1", "inconsistent_premises", ["pigeonhole"]),
    ("pigeonhole_2_1", ["p1h1", "p2h1", "~(p1h1 & p2h1)"], "p1h1", "inconsistent_premises", ["pigeonhole"]),
    # nested implication
    ("nested_mp", ["(a -> b) -> c", "a -> b"], "c", "entails", ["nested_implication"]),
    ("nested_curry", ["a -> (b -> c)", "a", "b"], "c", "entails", ["nested_implication"]),
    ("nested_mt", ["(a -> b) -> c", "~c"], "~(a -> b)", "entails", ["nested_implication"]),
    ("nested_invalid", ["a -> (b -> c)", "b"], "c", "does_not_entail", ["nested_implication"]),
    ("peirce_tautology", [], "((a -> b) -> a) -> a", "entails", ["nested_implication", "tautology"]),
    # vacuous truth
    ("vacuous_true", ["~a"], "a -> b", "entails", ["vacuous_truth"]),
    ("vacuous_contradiction_consequent", ["~a"], "a -> (b & ~b)", "entails", ["vacuous_truth"]),
    ("vacuous_invalid", ["~a"], "b -> a", "does_not_entail", ["vacuous_truth"]),
    # material implication
    ("material_true_consequent", ["b"], "a -> b", "entails", ["material_implication"]),
    ("material_true_antecedent", ["a"], "b -> a", "entails", ["material_implication"]),
    ("material_def_fwd", ["~a | b"], "a -> b", "entails", ["material_implication"]),
    ("material_def_bwd", ["a -> b"], "~a | b", "entails", ["material_implication"]),
    ("material_converse_invalid", ["a -> b"], "b -> a", "does_not_entail", ["material_implication"]),
    # boolean algebra
    ("demorgan_and", ["~(a & b)"], "~a | ~b", "entails", ["boolean"]),
    ("demorgan_or", ["~(a | b)"], "~a & ~b", "entails", ["boolean"]),
    ("distribute_and_over_or", ["a & (b | c)"], "(a & b) | (a & c)", "entails", ["boolean"]),
    ("distribute_or_over_and", ["(a | b) & (a | c)"], "a | (b & c)", "entails", ["boolean"]),
    ("or_does_not_give_and", ["a | b"], "a & b", "does_not_entail", ["boolean"]),
    # biconditional
    ("iff_mp", ["a <-> b", "a"], "b", "entails", ["biconditional"]),
    ("iff_mt", ["a <-> b", "~a"], "~b", "entails", ["biconditional"]),
    ("iff_underdetermined", ["a <-> b"], "a", "does_not_entail", ["biconditional"]),
    ("iff_transitive", ["a <-> b", "b <-> c"], "a <-> c", "entails", ["biconditional"]),
    # resolution
    ("resolution_c", ["a | b", "~a | c", "~b | c"], "c", "entails", ["resolution"]),
    ("resolution_a", ["a | b", "~b | c", "~c"], "a", "entails", ["resolution"]),
    ("unit_resolution", ["a | b | c", "~a", "~b"], "c", "entails", ["resolution"]),
]


def _compute(op, premises, conclusion):
    if op == "fol_prove":
        return fol_prove(premises, conclusion)["verdict"]
    if op == "check_consistency":
        return check_consistency(premises)["verdict"]
    return entails(premises, conclusion)["verdict"]


def build():
    BENCH.mkdir(exist_ok=True)
    with open(BENCH / "oracle_validation.jsonl", "w", encoding="utf-8") as fh:
        for row in ORACLE_VALIDATION:
            got = _compute(row["op"], row["premises"], row.get("conclusion"))
            assert got == row["gold"], f"oracle {row['id']}: Z3 {got} != gold {row['gold']}"
            fh.write(json.dumps(row) + "\n")

    with open(BENCH / "subagent_propositional.jsonl", "w", encoding="utf-8") as fh:
        for sid, premises, conclusion, expected, tags in _S:
            gold = entails(premises, conclusion)["verdict"]
            assert gold == expected, f"{sid}: Z3 {gold} != expected {expected}"
            fh.write(json.dumps({
                "id": sid, "op": "entails", "raw": f"benchmark:{sid}",
                "premises": premises, "conclusion": conclusion,
                "gold": gold, "tags": tags,
            }) + "\n")
    print(f"ok: {len(ORACLE_VALIDATION)} oracle, {len(_S)} subagent items")


if __name__ == "__main__":
    build()

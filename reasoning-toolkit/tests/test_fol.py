import z3

from reasoning_servers._fol_encode import _verdict_for
from reasoning_servers.formal_logic import fol_prove


def test_pendulum_fol_provable():
    # Trace Ledger solver log (dyad T9-T12): provable once the rule binds per account.
    premises = [
        "forall A, (IsObservation(A) -> StableAbsentNewEvidence(A))",
        "forall A, (RevisedUnderPromptingAlone(A) -> ~StableAbsentNewEvidence(A))",
        "RevisedUnderPromptingAlone(account_a)",
        "RevisedUnderPromptingAlone(account_b)",
    ]
    conclusion = "~IsObservation(account_a) & ~IsObservation(account_b)"
    assert fol_prove(premises, conclusion)["verdict"] == "provable"


def test_054_meta_theorem_provable():
    # Trace Ledger solver log (054 T28): the meta-theorem as written.
    premises = ["Uses(s, fq, q0)", "~ExplicitAccept(s, fq)"]
    conclusion = "~(forall F, forall Q, (Uses(s, F, Q) -> ExplicitAccept(s, F)))"
    assert fol_prove(premises, conclusion)["verdict"] == "provable"


def test_fol_refuted_returns_countermodel():
    res = fol_prove(["forall X, (P(X) -> Q(X))", "P(a)"], "Q(b)")
    assert res["verdict"] == "refuted"
    assert res["countermodel"]


def test_fol_unparenthesized_quantifier_scope():
    # Quantifier scope must extend to the right: `forall X, Man(X) -> Mortal(X)`
    # binds X in BOTH predicates. The classic syllogism must be provable.
    res = fol_prove(["forall X, Man(X) -> Mortal(X)", "Man(socrates)"], "Mortal(socrates)")
    assert res["verdict"] == "provable"


def test_fol_verdict_mapping_includes_unknown():
    # Z3 is not a decision procedure for FOL: `unknown` is a real outcome the
    # classifier must surface (not crash, not error).
    assert _verdict_for(z3.unsat) == "provable"
    assert _verdict_for(z3.sat) == "refuted"
    assert _verdict_for(z3.unknown) == "unknown"

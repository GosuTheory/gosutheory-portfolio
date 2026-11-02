from reasoning_servers.formal_logic import check_consistency, entails


def test_entails_true():
    assert entails(["a", "a -> b"], "b")["verdict"] == "entails"


def test_pendulum_propositional_does_not_entail():
    # Trace Ledger section 5: the bare-proposition encoding fails to entail.
    premises = [
        "is_observation -> stable_absent_new_evidence",
        "revised_under_prompting_alone -> ~stable_absent_new_evidence",
        "account_A_revised_under_prompting_alone",
        "account_B_revised_under_prompting_alone",
    ]
    conclusion = "~account_A_is_observation & ~account_B_is_observation"
    res = entails(premises, conclusion)
    assert res["verdict"] == "does_not_entail"
    assert res["counterexample"]  # a real satisfying assignment, non-empty


def test_inconsistent_premises():
    assert entails(["a", "~a"], "b")["verdict"] == "inconsistent_premises"


def test_consistency_vacuous_all_false_flagged():
    res = check_consistency(["a -> b", "b -> c"])
    assert res["verdict"] == "consistent"
    assert "all-false" in res["detail"]


def test_syntax_error_verdict():
    res = entails(["a &amp; b"], "b")
    assert res["verdict"] == "error"
    assert res["position"] == 6

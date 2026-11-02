from reasoning_servers.ledger import Ledger


def _mk(tmp_path):
    return Ledger(str(tmp_path / "ledger.db"))


def test_record_and_compare_labels_against_oracle(tmp_path):
    led = _mk(tmp_path)
    led.register_problem("p1", "formal-logic", "s", "raw", "{}", "test")
    led.record_run("p1", "formal-logic", "local", "entails", "ih", "oh1",
                   "entails", "", 1, None, "measured", 1)
    led.record_run("p1", "formal-logic", "subagent", "entails", "ih", "oh2",
                   "does_not_entail", "", 2, "model-x", "asserted", 0)
    cmp = led.compare("p1")
    assert cmp["oracle_verdict"] == "entails"
    assert cmp["lanes"]["subagent"]["label"] == "incorrect"


def test_metrics_wilson_ci(tmp_path):
    led = _mk(tmp_path)
    for i in range(10):  # oracle definite on all 10; subagent agrees on 8
        pid = f"p{i}"
        led.register_problem(pid, "formal-logic", "bench", "raw", "{}", "test")
        led.record_run(pid, "formal-logic", "local", "entails", "ih", f"o{i}",
                       "entails", "", 1, None, "measured", 1)
        sub = "entails" if i < 8 else "does_not_entail"
        led.record_run(pid, "formal-logic", "subagent", "entails", "ih", f"s{i}",
                       sub, "", 1, "m", "asserted", 0)
    m = led.metrics("formal-logic", "subagent", "bench")
    assert m["agreement"] == 0.8
    assert abs(m["wilson_lo"] - 0.490) < 0.001
    assert abs(m["wilson_hi"] - 0.943) < 0.001


def test_coverage_counts_unparseable_as_wrong(tmp_path):
    led = _mk(tmp_path)
    verdicts = ["entails"] * 5 + ["does_not_entail"] * 3 + ["unparseable"] * 2
    for i, v in enumerate(verdicts):
        pid = f"p{i}"
        led.register_problem(pid, "formal-logic", "bench", "raw", "{}", "test")
        led.record_run(pid, "formal-logic", "local", "entails", "ih", f"o{i}",
                       "entails", "", 1, None, "measured", 1)
        led.record_run(pid, "formal-logic", "subagent", "entails", "ih", f"s{i}",
                       v, "", 1, "m", "asserted", 0)
    m = led.metrics("formal-logic", "subagent", "bench")
    assert m["coverage"] == 0.8
    assert m["answered_correct_over_all"] == 0.5


def test_oracle_unknown_excluded_and_counted(tmp_path):
    led = _mk(tmp_path)
    for i in range(6):  # oracle unknown on 2 (excluded); definite on 4; subagent matches
        pid = f"p{i}"
        led.register_problem(pid, "formal-logic", "fol", "raw", "{}", "test")
        ov = "unknown" if i < 2 else "provable"
        led.record_run(pid, "formal-logic", "local", "fol_prove", "ih", f"o{i}",
                       ov, "", 1, None, "measured", 1)
        led.record_run(pid, "formal-logic", "subagent", "fol_prove", "ih", f"s{i}",
                       "provable", "", 1, "m", "asserted", 0)
    m = led.metrics("formal-logic", "subagent", "fol")
    assert m["oracle_unknown"] == 2
    assert m["n"] == 4
    assert m["agreement"] == 1.0

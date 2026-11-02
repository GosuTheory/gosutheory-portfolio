"""formal_logic MCP server: propositional entails / check_consistency (Z3).

The propositional lane is a COMPLETE oracle: Z3 always returns sat/unsat over
Boolean constants. Tool functions are plain and importable; the MCP wiring at
the bottom is a thin shell.
"""
import z3

from ._z3_encode import ParseError, parse_prop


def _model_to_dict(model, env):
    out = {}
    for name, const in env.items():
        val = model.evaluate(const, model_completion=True)
        out[name] = bool(z3.is_true(val))
    return out


def _parse_error_result(err):
    return {
        "verdict": "error",
        "detail": err.message,
        "position": err.position,
        "counterexample": None,
        "model": None,
    }


def entails(premises: list[str], conclusion: str) -> dict:
    """Propositional entailment by refutation, with an inconsistent-premises guard."""
    env: dict = {}
    try:
        prem = [parse_prop(p, env) for p in premises]
        concl = parse_prop(conclusion, env)
    except ParseError as err:
        return _parse_error_result(err)

    guard = z3.Solver()
    guard.add(*prem)
    if guard.check() == z3.unsat:
        return {
            "verdict": "inconsistent_premises",
            "detail": "premises are unsatisfiable on their own; they entail everything vacuously",
            "position": None,
            "counterexample": None,
            "model": None,
        }

    solver = z3.Solver()
    solver.add(*prem)
    solver.add(z3.Not(concl))
    result = solver.check()
    if result == z3.unsat:
        return {
            "verdict": "entails",
            "detail": "premises ∧ ¬conclusion is unsatisfiable",
            "position": None,
            "counterexample": None,
            "model": None,
        }
    if result == z3.sat:
        return {
            "verdict": "does_not_entail",
            "detail": "found an assignment satisfying the premises but not the conclusion",
            "position": None,
            "counterexample": _model_to_dict(solver.model(), env),
            "model": None,
        }
    return {
        "verdict": "error",
        "detail": "solver returned unknown on a propositional problem",
        "position": None,
        "counterexample": None,
        "model": None,
    }


def check_consistency(formulas: list[str]) -> dict:
    """Are the formulas jointly satisfiable? Flags the all-false (vacuous) model."""
    env: dict = {}
    try:
        parsed = [parse_prop(f, env) for f in formulas]
    except ParseError as err:
        return _parse_error_result(err)

    solver = z3.Solver()
    solver.add(*parsed)
    result = solver.check()
    if result == z3.unsat:
        return {"verdict": "inconsistent", "detail": "no satisfying model",
                "position": None, "counterexample": None, "model": None}
    if result != z3.sat:
        return {"verdict": "error", "detail": "solver returned unknown",
                "position": None, "counterexample": None, "model": None}

    model = _model_to_dict(solver.model(), env)
    detail = "jointly satisfiable"
    if env:
        allfalse = z3.Solver()
        allfalse.add(*parsed)
        allfalse.add(*[z3.Not(c) for c in env.values()])
        if allfalse.check() == z3.sat:
            detail = ("jointly satisfiable, but the all-false assignment is a model "
                      "(vacuous: atoms are related but none asserted)")
    return {"verdict": "consistent", "detail": detail,
            "position": None, "counterexample": None, "model": model}


# --- MCP wiring (thin shell; not exercised by unit tests) ---
def main():  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("formal_logic")
    mcp.tool(name="entails")(entails)
    mcp.tool(name="check_consistency")(check_consistency)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

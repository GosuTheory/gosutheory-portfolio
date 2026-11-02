import pytest
import z3

from reasoning_servers._z3_encode import ParseError, parse_prop


def test_parses_implication():
    env = {}
    parsed = parse_prop("a -> b", env)
    expected = z3.Implies(env["a"], env["b"])
    assert z3.eq(parsed, expected)


def test_precedence():
    env = {}
    parsed = parse_prop("~a & b -> c", env)
    expected = z3.Implies(z3.And(z3.Not(env["a"]), env["b"]), env["c"])
    assert z3.eq(parsed, expected)


def test_rejects_html_escaped_amp():
    env = {}
    with pytest.raises(ParseError) as exc:
        parse_prop("a &amp; b", env)
    assert exc.value.position == 6  # the ';' in "a &amp; b"


def test_rejects_unbalanced_paren():
    env = {}
    with pytest.raises(ParseError):
        parse_prop("(a & b", env)

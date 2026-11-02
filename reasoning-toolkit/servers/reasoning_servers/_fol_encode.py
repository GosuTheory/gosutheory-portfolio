"""First-order fragment → Z3 encoder.

Supports: `forall`/`exists` over a single sort, predicate application with
constants and bound variables (`P(x)`, `Uses(s, F, Q)`), nullary atoms, and
`~ & | -> <->`. One FOLContext is shared across a prove call so a predicate
keeps one arity and constants are shared across premises and conclusion.

Z3 does not decide full FOL, so a prove call can come back `unknown`; that is a
real verdict, surfaced by `_verdict_for`.
"""
import z3

from ._z3_encode import ParseError

_KEYWORDS = {"forall", "exists"}


class FOLContext:
    def __init__(self):
        self.sort = z3.DeclareSort("U")
        self.predicates = {}   # name -> (z3.FuncDecl, arity)
        self.nullary = {}      # name -> z3.BoolRef
        self.constants = {}    # name -> z3.Const

    def predicate(self, name, arity, position):
        if name in self.predicates:
            fn, known = self.predicates[name]
            if known != arity:
                raise ParseError(
                    f"predicate {name!r} used with arity {arity} after arity {known}",
                    position,
                )
            return fn
        if name in self.nullary:
            raise ParseError(f"{name!r} used as both atom and predicate", position)
        fn = z3.Function(name, *([self.sort] * arity), z3.BoolSort())
        self.predicates[name] = (fn, arity)
        return fn

    def nullary_atom(self, name, position):
        if name in self.predicates:
            raise ParseError(f"{name!r} used as both predicate and atom", position)
        if name not in self.nullary:
            self.nullary[name] = z3.Bool(name)
        return self.nullary[name]

    def constant(self, name):
        if name not in self.constants:
            self.constants[name] = z3.Const(name, self.sort)
        return self.constants[name]


def _tokenize(s):
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "<":
            if s[i : i + 3] == "<->":
                toks.append(("IFF", i)); i += 3; continue
            raise ParseError(f"Unexpected character {c!r} at position {i}", i)
        if c == "-":
            if s[i : i + 2] == "->":
                toks.append(("IMP", i)); i += 2; continue
            raise ParseError(f"Unexpected character {c!r} at position {i}", i)
        if c == "|":
            toks.append(("OR", i)); i += 1; continue
        if c == "&":
            toks.append(("AND", i)); i += 1; continue
        if c == "~":
            toks.append(("NOT", i)); i += 1; continue
        if c == "(":
            toks.append(("LP", i)); i += 1; continue
        if c == ")":
            toks.append(("RP", i)); i += 1; continue
        if c == ",":
            toks.append(("COMMA", i)); i += 1; continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("NAME", i, s[i:j])); i = j; continue
        raise ParseError(f"Unexpected character {c!r} at position {i}", i)
    toks.append(("EOF", n))
    return toks


class _FOLParser:
    def __init__(self, toks, ctx):
        self.toks = toks
        self.pos = 0
        self.ctx = ctx
        self.scope = []  # list of {varname: z3.Const}

    def _peek(self):
        return self.toks[self.pos]

    def _advance(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _expect(self, kind):
        t = self._peek()
        if t[0] != kind:
            raise ParseError(f"Expected {kind} at position {t[1]}", t[1])
        return self._advance()

    def parse(self):
        expr = self._iff()
        t = self._peek()
        if t[0] != "EOF":
            raise ParseError(f"Unexpected token at position {t[1]}", t[1])
        return expr

    def _iff(self):
        left = self._imp()
        while self._peek()[0] == "IFF":
            self._advance()
            left = left == self._imp()
        return left

    def _imp(self):
        left = self._or()
        if self._peek()[0] == "IMP":
            self._advance()
            return z3.Implies(left, self._imp())
        return left

    def _or(self):
        left = self._and()
        while self._peek()[0] == "OR":
            self._advance()
            left = z3.Or(left, self._and())
        return left

    def _and(self):
        left = self._unary()
        while self._peek()[0] == "AND":
            self._advance()
            left = z3.And(left, self._unary())
        return left

    def _unary(self):
        t = self._peek()
        if t[0] == "NOT":
            self._advance()
            return z3.Not(self._unary())
        if t[0] == "NAME" and t[2] in _KEYWORDS:
            return self._quant()
        return self._atom()

    def _quant(self):
        kw = self._advance()  # forall / exists
        var = self._expect("NAME")
        self._expect("COMMA")
        const = z3.Const(var[2], self.ctx.sort)
        self.scope.append({var[2]: const})
        body = self._unary()
        self.scope.pop()
        if kw[2] == "forall":
            return z3.ForAll([const], body)
        return z3.Exists([const], body)

    def _atom(self):
        t = self._peek()
        if t[0] == "LP":
            self._advance()
            expr = self._iff()
            self._expect("RP")
            return expr
        if t[0] == "NAME":
            return self._predicate()
        raise ParseError(f"Expected atom or '(' at position {t[1]}", t[1])

    def _predicate(self):
        name_tok = self._advance()  # NAME
        name, position = name_tok[2], name_tok[1]
        if self._peek()[0] == "LP":
            self._advance()
            args = [self._term()]
            while self._peek()[0] == "COMMA":
                self._advance()
                args.append(self._term())
            self._expect("RP")
            fn = self.ctx.predicate(name, len(args), position)
            return fn(*args)
        return self.ctx.nullary_atom(name, position)

    def _term(self):
        t = self._expect("NAME")
        name = t[2]
        for frame in reversed(self.scope):
            if name in frame:
                return frame[name]
        return self.ctx.constant(name)


def parse_fol(formula, ctx):
    return _FOLParser(_tokenize(formula), ctx).parse()


def _verdict_for(result):
    """Map a Z3 CheckSatResult to a fol_prove verdict."""
    if result == z3.unsat:
        return "provable"
    if result == z3.sat:
        return "refuted"
    return "unknown"

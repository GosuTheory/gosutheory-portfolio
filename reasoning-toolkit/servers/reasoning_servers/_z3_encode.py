"""Surface-syntax → Z3 encoder for the propositional fragment.

Operators, lowest to highest precedence: `<->`, `->` (right-assoc), `|`, `&`,
unary `~`, then atoms / parentheses. Atoms match [A-Za-z_][A-Za-z0-9_]*.
Parsing populates `env` with a `z3.Bool` per distinct atom.
"""
import z3


class ParseError(Exception):
    def __init__(self, message, position=None):
        super().__init__(message)
        self.message = message
        self.position = position


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
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("NAME", i, s[i:j])); i = j; continue
        raise ParseError(f"Unexpected character {c!r} at position {i}", i)
    toks.append(("EOF", n))
    return toks


class _Parser:
    def __init__(self, toks, env):
        self.toks = toks
        self.pos = 0
        self.env = env

    def _peek(self):
        return self.toks[self.pos]

    def _advance(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

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
            left = left == self._imp()  # Bool equality is logical iff in Z3
        return left

    def _imp(self):
        left = self._or()
        if self._peek()[0] == "IMP":
            self._advance()
            return z3.Implies(left, self._imp())  # right-associative
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
        if self._peek()[0] == "NOT":
            self._advance()
            return z3.Not(self._unary())
        return self._atom()

    def _atom(self):
        t = self._peek()
        if t[0] == "NAME":
            self._advance()
            name = t[2]
            if name not in self.env:
                self.env[name] = z3.Bool(name)
            return self.env[name]
        if t[0] == "LP":
            self._advance()
            expr = self._iff()
            if self._peek()[0] != "RP":
                nxt = self._peek()
                raise ParseError(f"Expected ')' at position {nxt[1]}", nxt[1])
            self._advance()
            return expr
        raise ParseError(f"Expected atom or '(' at position {t[1]}", t[1])


def parse_prop(formula, env):
    """Parse a propositional formula string into a Z3 BoolRef, filling `env`."""
    return _Parser(_tokenize(formula), env).parse()

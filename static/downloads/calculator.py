#!/usr/bin/env python3
"""A small, safe CLI calculator.

Type expressions and it evaluates them with correct operator precedence.
No `eval()` -- input is parsed with the `ast` module and only a whitelist
of operations is allowed, so it can't be used to run arbitrary code.

Usage:
    python calculator.py              # interactive REPL
    python calculator.py "2 + 3 * 4"  # one-shot mode

REPL commands:
    :help     show help
    :quit     exit (also :q, Ctrl-D)
    ans       the previous result
    x         recall the previous result (shorthand)
"""

from __future__ import annotations

import ast
import math
import operator
import sys

# ---------------------------------------------------------------------------
# Safe evaluation
# ---------------------------------------------------------------------------

# Binary operators we permit, mapped to their implementations.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Unary operators (e.g. -5, +5).
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Named helpers available inside expressions.
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
}

# Named constants.
_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


class CalcError(Exception):
    """A user-facing calculation error (bad expression, domain error, etc.)."""


def _eval_node(node: ast.AST, names: dict[str, float]) -> float:
    """Recursively evaluate a whitelisted AST node and return a number."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)

    # A bare number literal.
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalcError(f"unsupported literal: {node.value!r}")

    # Binary op: a <op> b
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise CalcError(f"operator not allowed: {op_type.__name__}")
        left = _eval_node(node.left, names)
        right = _eval_node(node.right, names)
        try:
            return _BIN_OPS[op_type](left, right)
        except ZeroDivisionError:
            raise CalcError("division by zero")
        except OverflowError:
            raise CalcError("result too large")

    # Unary op: -a, +a
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise CalcError(f"operator not allowed: {op_type.__name__}")
        return _UNARY_OPS[op_type](_eval_node(node.operand, names))

    # Named constants: pi, e, tau, ans, x
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise CalcError(f"unknown name: {node.id!r}")

    # Function calls: sqrt(2), log(8, 2), round(pi, 3)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise CalcError("call to unsupported function")
        if node.keywords:
            raise CalcError("keyword arguments are not supported")
        args = [_eval_node(a, names) for a in node.args]
        try:
            return _FUNCTIONS[node.func.id](*args)
        except TypeError as exc:
            raise CalcError(f"bad arguments to {node.func.id}: {exc}")
        except ValueError:
            raise CalcError(f"math domain error in {node.func.id}")

    raise CalcError(f"unsupported syntax: {type(node).__name__}")


def evaluate(expression: str, previous: float | None = None) -> float:
    """Evaluate a math expression string and return a float.

    Raises CalcError (with a human-readable message) on any bad input.
    """
    expression = expression.strip()
    if not expression:
        raise CalcError("empty expression")

    # `^` is not Python's power operator -- users expect it to be. Map to **,
    # unless it looks like a bitwise xor (which we don't support anyway).
    expression = expression.replace("^", "**")

    names: dict[str, float] = {}
    if previous is not None:
        names["ans"] = previous
        names["x"] = previous

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"syntax error: {exc.msg}")

    return _eval_node(tree, names)


def format_number(value: float) -> str:
    """Render a float the way a human wants to see it (no float noise)."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    # Trim float noise while keeping meaningful precision.
    return f"{value:.12g}"


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------

_BANNER = """\
CLI Calculator  --  type an expression, or :help for commands.
Examples:  (2 + 3) * 4      2^10      sqrt(2)      pi * 5^2
"""

_HELP = """\
Commands:
  :help, :h     show this help
  :quit, :q     exit
  ans or x      the previous result

Operators:  + - * / // % ** (or ^)
Functions:  sqrt abs round floor ceil sin cos tan log log10 log2 exp
Constants:  pi e tau
"""


def repl() -> int:
    print(_BANNER)
    previous: float | None = None

    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()  # tidy newline after Ctrl-D / Ctrl-C
            return 0

        stripped = line.strip()
        if not stripped:
            continue

        if stripped in (":quit", ":q", ":exit"):
            return 0
        if stripped in (":help", ":h"):
            print(_HELP)
            continue
        if stripped.startswith(":"):
            print(f"unknown command {stripped!r} -- try :help")
            continue

        try:
            result = evaluate(stripped, previous)
        except CalcError as exc:
            print(f"error: {exc}")
            continue

        previous = result
        print(f"= {format_number(result)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) > 1:
        expression = " ".join(argv[1:])
        try:
            result = evaluate(expression)
        except CalcError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(format_number(result))
        return 0

    return repl()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

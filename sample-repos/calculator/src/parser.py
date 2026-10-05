"""Expression parser and evaluator for the calculator."""

import re
from typing import Any
from calculator import Calculator


class ExpressionParser:
    """Parses and evaluates mathematical expressions."""

    OPERATORS = {
        '+': ('add', 1),
        '-': ('subtract', 1),
        '*': ('multiply', 2),
        '/': ('divide', 2),
        '^': ('power', 3),
    }

    def __init__(self, calculator: Calculator):
        self.calculator = calculator

    def evaluate(self, expression: str) -> float:
        """Evaluate a mathematical expression string.

        Supports: +, -, *, /, ^, parentheses
        """
        tokens = self._tokenize(expression)
        result = self._parse_expression(tokens, 0)
        return result[0]

    def _tokenize(self, expression: str) -> list[str]:
        """Tokenize the expression into numbers and operators."""
        tokens = []
        current = ""

        for char in expression.replace(" ", ""):
            if char in "0123456789.":
                current += char
            else:
                if current:
                    tokens.append(current)
                    current = ""
                if char in self.OPERATORS or char in "()":
                    tokens.append(char)

        if current:
            tokens.append(current)

        return tokens

    def _parse_expression(
        self, tokens: list[str], pos: int
    ) -> tuple[float, int]:
        """Parse expression with operator precedence."""
        left, pos = self._parse_term(tokens, pos)

        while pos < len(tokens) and tokens[pos] in ('+', '-'):
            op = tokens[pos]
            pos += 1
            right, pos = self._parse_term(tokens, pos)

            if op == '+':
                left = self.calculator.add(left, right)
            else:
                left = self.calculator.subtract(left, right)

        return left, pos

    def _parse_term(
        self, tokens: list[str], pos: int
    ) -> tuple[float, int]:
        """Parse multiplication/division terms."""
        left, pos = self._parse_factor(tokens, pos)

        while pos < len(tokens) and tokens[pos] in ('*', '/'):
            op = tokens[pos]
            pos += 1
            right, pos = self._parse_factor(tokens, pos)

            if op == '*':
                left = self.calculator.multiply(left, right)
            else:
                left = self.calculator.divide(left, right)

        return left, pos

    def _parse_factor(
        self, tokens: list[str], pos: int
    ) -> tuple[float, int]:
        """Parse atomic values and parenthesized expressions."""
        if pos >= len(tokens):
            raise ValueError("Unexpected end of expression")

        if tokens[pos] == '(':
            result, pos = self._parse_expression(tokens, pos + 1)
            if pos < len(tokens) and tokens[pos] == ')':
                pos += 1
            return result, pos

        try:
            return float(tokens[pos]), pos + 1
        except ValueError:
            raise ValueError(f"Invalid token: {tokens[pos]}")


def format_result(value: float, precision: int = 6) -> str:
    """Format a numerical result for display."""
    if value == int(value):
        return str(int(value))
    return f"{value:.{precision}f}".rstrip('0').rstrip('.')

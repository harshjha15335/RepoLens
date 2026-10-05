"""Calculator application - sample repository for CodeMentor-RAG evaluation."""


class Calculator:
    """A basic calculator with history tracking."""

    def __init__(self):
        self.history: list[str] = []
        self.last_result: float = 0

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self._record(f"{a} + {b} = {result}")
        self.last_result = result
        return result

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        result = a - b
        self._record(f"{a} - {b} = {result}")
        self.last_result = result
        return result

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        result = a * b
        self._record(f"{a} * {b} = {result}")
        self.last_result = result
        return result

    def divide(self, a: float, b: float) -> float:
        """Divide a by b. Raises ValueError for division by zero."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self._record(f"{a} / {b} = {result}")
        self.last_result = result
        return result

    def power(self, base: float, exponent: float) -> float:
        """Raise base to the power of exponent."""
        result = base ** exponent
        self._record(f"{base} ^ {exponent} = {result}")
        self.last_result = result
        return result

    def _record(self, entry: str) -> None:
        """Record an operation in history."""
        self.history.append(entry)

    def get_history(self) -> list[str]:
        """Get the operation history."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear the operation history."""
        self.history.clear()
        self.last_result = 0

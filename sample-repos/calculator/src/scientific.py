"""Scientific calculator extending the basic Calculator."""

import math
from calculator import Calculator


class ScientificCalculator(Calculator):
    """Extended calculator with scientific operations."""

    def __init__(self):
        super().__init__()
        self.angle_mode = "radians"  # or "degrees"

    def set_angle_mode(self, mode: str) -> None:
        """Set angle mode to 'radians' or 'degrees'."""
        if mode not in ("radians", "degrees"):
            raise ValueError(f"Invalid angle mode: {mode}")
        self.angle_mode = mode

    def sqrt(self, x: float) -> float:
        """Calculate square root."""
        if x < 0:
            raise ValueError("Cannot compute square root of negative number")
        result = math.sqrt(x)
        self._record(f"sqrt({x}) = {result}")
        self.last_result = result
        return result

    def log(self, x: float, base: float = math.e) -> float:
        """Calculate logarithm with optional base."""
        if x <= 0:
            raise ValueError("Logarithm input must be positive")
        result = math.log(x, base)
        self._record(f"log_{base}({x}) = {result}")
        self.last_result = result
        return result

    def sin(self, angle: float) -> float:
        """Calculate sine of angle."""
        if self.angle_mode == "degrees":
            angle = math.radians(angle)
        result = math.sin(angle)
        self._record(f"sin({angle}) = {result}")
        self.last_result = result
        return result

    def cos(self, angle: float) -> float:
        """Calculate cosine of angle."""
        if self.angle_mode == "degrees":
            angle = math.radians(angle)
        result = math.cos(angle)
        self._record(f"cos({angle}) = {result}")
        self.last_result = result
        return result

    def factorial(self, n: int) -> int:
        """Calculate factorial of n."""
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        result = math.factorial(n)
        self._record(f"{n}! = {result}")
        self.last_result = float(result)
        return result

# Sample Calculator

A Python calculator application with basic and scientific operations.

## Features

- Basic arithmetic: add, subtract, multiply, divide
- Scientific operations: sqrt, log, sin, cos, factorial
- Expression parsing with operator precedence
- Operation history tracking
- Angle mode support (radians/degrees)

## Architecture

The calculator is organized into three main modules:

1. **calculator.py** - Base `Calculator` class with arithmetic operations and history
2. **scientific.py** - `ScientificCalculator` extending the base with math functions
3. **parser.py** - `ExpressionParser` for evaluating expression strings

## Usage

```python
from calculator import Calculator
from scientific import ScientificCalculator
from parser import ExpressionParser

# Basic usage
calc = Calculator()
result = calc.add(2, 3)  # 5

# Scientific
sci = ScientificCalculator()
sci.set_angle_mode("degrees")
result = sci.sin(90)  # 1.0

# Expression parsing
parser = ExpressionParser(calc)
result = parser.evaluate("2 + 3 * 4")  # 14
```

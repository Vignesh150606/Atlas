import ast
import operator
from typing import Any
from app.tools.base import Tool, ToolResult

# Deliberately not using eval()/exec() - only a whitelisted set of arithmetic
# AST node types are allowed, so this can't execute arbitrary code even if
# the "expression" contains something malicious.
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class CalculatorError(Exception):
    pass


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise CalculatorError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_fn = _ALLOWED_OPERATORS.get(type(node.op))
        if op_fn is None:
            raise CalculatorError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _ALLOWED_OPERATORS.get(type(node.op))
        if op_fn is None:
            raise CalculatorError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.operand))
    raise CalculatorError(f"Unsupported expression: {type(node).__name__}")


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluates a basic arithmetic expression (+ - * / ** % //)."

    async def run(self, expression: str = "", **kwargs: Any) -> ToolResult:
        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)
            return ToolResult(tool_name=self.name, success=True, output=result)
        except (CalculatorError, SyntaxError, ZeroDivisionError, TypeError) as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))

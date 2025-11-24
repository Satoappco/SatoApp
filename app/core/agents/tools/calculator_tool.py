"""Calculator tool for performing mathematical operations."""

import logging
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field
import ast
import operator

logger = logging.getLogger(__name__)


class CalculatorTool(BaseTool):
    """Tool for performing mathematical calculations.

    This tool can evaluate mathematical expressions safely using Python's
    ast module to prevent code injection attacks. It supports:
    - Basic arithmetic: +, -, *, /, //, %, **
    - Parentheses for grouping
    - Numbers (integers and floats)

    Examples:
    - "2 + 2" -> 4
    - "(10 + 5) * 3" -> 45
    - "100 / 4" -> 25.0
    - "2 ** 8" -> 256
    """

    name: str = "calculator"
    description: str = """Performs mathematical calculations.

    Input should be a valid mathematical expression string containing:
    - Numbers (integers or floats)
    - Basic operators: +, -, *, /, //, %, **
    - Parentheses for grouping

    Examples:
    - "2 + 2"
    - "(10 + 5) * 3"
    - "100 / 4"
    - "2 ** 8"
    - "(1500 - 500) * 0.15"

    Returns the calculated result as a string.
    """

    # Thread ID for tracing (optional)
    thread_id: Optional[str] = Field(default=None, description="Thread ID for tracing")
    level: int = Field(default=1, description="Hierarchy level for tracing")

    # Supported operators
    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,  # Unary minus
    }

    def _run(self, expression: str) -> str:
        """Execute a mathematical calculation.

        Args:
            expression: Mathematical expression string

        Returns:
            String containing the calculation result or error message
        """
        import time
        start_time = time.time()

        try:
            # Clean the expression
            expression = expression.strip()

            logger.info(f"🧮 [CalculatorTool] Evaluating expression: {expression}")

            # Parse and evaluate the expression safely
            result = self._safe_eval(expression)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Format result
            output = f"{result}"

            logger.info(f"✅ [CalculatorTool] Result: {output}")

            # Trace tool usage if thread_id is available
            if self.thread_id:
                try:
                    from app.services.chat_trace_service import ChatTraceService
                    trace_service = ChatTraceService()
                    trace_service.add_tool_usage(
                        thread_id=self.thread_id,
                        tool_name="calculator",
                        tool_input=expression,
                        tool_output=output,
                        success=True,
                        latency_ms=latency_ms,
                        metadata={
                            "expression": expression,
                            "result": result
                        },
                        level=self.level
                    )
                except Exception as e:
                    logger.warning(f"⚠️  [CalculatorTool] Failed to trace tool usage: {e}")

            return output

        except Exception as e:
            error_msg = f"Calculation error: {str(e)}"
            logger.error(f"❌ [CalculatorTool] {error_msg}")

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Trace tool usage failure if thread_id is available
            if self.thread_id:
                try:
                    from app.services.chat_trace_service import ChatTraceService
                    trace_service = ChatTraceService()
                    trace_service.add_tool_usage(
                        thread_id=self.thread_id,
                        tool_name="calculator",
                        tool_input=expression,
                        tool_output=error_msg,
                        success=False,
                        error=str(e),
                        latency_ms=latency_ms,
                        metadata={
                            "expression": expression,
                            "error_type": type(e).__name__
                        },
                        level=self.level
                    )
                except Exception as trace_error:
                    logger.warning(f"⚠️  [CalculatorTool] Failed to trace tool error: {trace_error}")

            return error_msg

    async def _arun(self, expression: str) -> str:
        """Async version - falls back to sync implementation."""
        return self._run(expression)

    def _safe_eval(self, expression: str) -> float:
        """Safely evaluate a mathematical expression using AST.

        Args:
            expression: Mathematical expression string

        Returns:
            Numerical result of the calculation

        Raises:
            ValueError: If expression is invalid or contains unsupported operations
        """
        try:
            # Parse the expression into an AST
            node = ast.parse(expression, mode='eval').body

            # Recursively evaluate the AST
            return self._eval_node(node)

        except SyntaxError as e:
            raise ValueError(f"Invalid mathematical expression: {e}")
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {e}")

    def _eval_node(self, node):
        """Recursively evaluate an AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Numerical result of the node evaluation

        Raises:
            ValueError: If node type is unsupported
        """
        if isinstance(node, ast.Constant):
            # Python 3.8+ - numbers are Constant nodes
            return node.value

        elif isinstance(node, ast.Num):
            # Python 3.7 and earlier - numbers are Num nodes
            return node.n

        elif isinstance(node, ast.BinOp):
            # Binary operation (e.g., 2 + 3)
            op_type = type(node.op)
            if op_type not in self._operators:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")

            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self._operators[op_type](left, right)

        elif isinstance(node, ast.UnaryOp):
            # Unary operation (e.g., -5)
            op_type = type(node.op)
            if op_type not in self._operators:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

            operand = self._eval_node(node.operand)
            return self._operators[op_type](operand)

        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

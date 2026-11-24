"""AST-whitelisted safe expression parser compiling declarative EXPRESSION DSL to DuckDB SQL."""
import ast
import re
from typing import Set, Tuple


_DISALLOWED_SUBSTRINGS = (";", "--", "/*", "*/")
_RESERVED_SQL_NAMES = frozenset({"true", "false", "null"})


def _quote_ident(name: str) -> str:
	if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
		raise ValueError(f"Tên cột/định danh không hợp lệ trong biểu thức: '{name}'.")
	return f'"{name}"'


def parse_safe_expression(expr: str) -> Tuple[str, Set[str]]:
	"""Parses an arithmetic/boolean expression via AST whitelist into safe DuckDB SQL.

	Returns:
		(duckdb_sql_expression, referenced_column_identifiers)
	"""
	if not isinstance(expr, str) or not expr.strip():
		raise ValueError("Biểu thức (expr) không được để trống.")

	cleaned = expr.strip()
	for bad in _DISALLOWED_SUBSTRINGS:
		if bad in cleaned:
			raise ValueError(f"Biểu thức chứa chuỗi không được phép: '{bad}'.")

	try:
		tree = ast.parse(cleaned, mode="eval")
	except SyntaxError as exc:
		raise ValueError(f"Cú pháp biểu thức không hợp lệ: {exc.msg}.") from exc

	referenced: Set[str] = set()

	def _compile(node: ast.AST) -> str:
		if isinstance(node, ast.Expression):
			return _compile(node.body)

		if isinstance(node, ast.Constant):
			val = node.value
			if isinstance(val, bool):
				return "TRUE" if val else "FALSE"
			if isinstance(val, (int, float)):
				return repr(float(val)) if isinstance(val, float) else str(val)
			if isinstance(val, str):
				escaped = val.replace("'", "''")
				return f"'{escaped}'"
			if val is None:
				return "NULL"
			raise ValueError(f"Hằng số không được hỗ trợ trong biểu thức: {type(val).__name__}.")

		if isinstance(node, ast.Name):
			ident = node.id
			lower = ident.lower()
			if lower == "true":
				return "TRUE"
			if lower == "false":
				return "FALSE"
			if lower == "null":
				return "NULL"
			referenced.add(ident)
			return _quote_ident(ident)

		if isinstance(node, ast.UnaryOp):
			operand = _compile(node.operand)
			if isinstance(node.op, ast.USub):
				return f"(-({operand}))"
			if isinstance(node.op, ast.UAdd):
				return f"(+({operand}))"
			if isinstance(node.op, ast.Not):
				return f"(NOT ({operand}))"
			raise ValueError(f"Toán tử một ngôi không được hỗ trợ: {type(node.op).__name__}.")

		if isinstance(node, ast.BinOp):
			left = _compile(node.left)
			right = _compile(node.right)
			if isinstance(node.op, ast.Add):
				return f"({left} + {right})"
			if isinstance(node.op, ast.Sub):
				return f"({left} - {right})"
			if isinstance(node.op, ast.Mult):
				return f"({left} * {right})"
			if isinstance(node.op, ast.Div):
				return f"(CAST({left} AS DOUBLE) / NULLIF(CAST({right} AS DOUBLE), 0.0))"
			raise ValueError(f"Toán tử số học không được hỗ trợ: {type(node.op).__name__}.")

		if isinstance(node, ast.BoolOp):
			parts = [f"({_compile(v)})" for v in node.values]
			if isinstance(node.op, ast.And):
				return "(" + " AND ".join(parts) + ")"
			if isinstance(node.op, ast.Or):
				return "(" + " OR ".join(parts) + ")"
			raise ValueError(f"Toán tử logic không được hỗ trợ: {type(node.op).__name__}.")

		if isinstance(node, ast.Compare):
			if len(node.ops) != len(node.comparators):
				raise ValueError("Biểu thức so sánh không hợp lệ.")
			clauses = []
			prev = node.left
			op_map = {
				ast.Eq: "=",
				ast.NotEq: "!=",
				ast.Lt: "<",
				ast.LtE: "<=",
				ast.Gt: ">",
				ast.GtE: ">=",
			}
			for op, comp in zip(node.ops, node.comparators):
				op_sql = op_map.get(type(op))
				if op_sql is None:
					raise ValueError(f"Toán tử so sánh không được hỗ trợ: {type(op).__name__}.")
				clauses.append(f"({_compile(prev)} {op_sql} {_compile(comp)})")
				prev = comp
			return clauses[0] if len(clauses) == 1 else "(" + " AND ".join(clauses) + ")"

		if isinstance(node, ast.Call):
			if not isinstance(node.func, ast.Name) or node.keywords:
				raise ValueError("Chỉ cho phép gọi hàm whitelist với tham số vị trí.")
			fn = node.func.id
			args = [_compile(a) for a in node.args]

			if fn == "abs" and len(args) == 1:
				return f"ABS(CAST({args[0]} AS DOUBLE))"
			if fn == "log1p" and len(args) == 1:
				return f"LN(1.0 + GREATEST(CAST({args[0]} AS DOUBLE), 0.0))"
			if fn == "sin" and len(args) == 1:
				return f"SIN(CAST({args[0]} AS DOUBLE))"
			if fn == "cos" and len(args) == 1:
				return f"COS(CAST({args[0]} AS DOUBLE))"
			if fn == "clip" and len(args) == 3:
				return f"LEAST(GREATEST(CAST({args[0]} AS DOUBLE), CAST({args[1]} AS DOUBLE)), CAST({args[2]} AS DOUBLE))"
			if fn == "coalesce" and len(args) >= 2:
				return f"COALESCE({', '.join(args)})"
			if fn == "extract_hour" and len(args) == 1:
				# Use normalized _ts column when passed the canonical timestamp col, or direct timestamp
				return f"CAST(EXTRACT(HOUR FROM _ts) AS DOUBLE)" if args[0] == '"timestamp"' else f"CAST(EXTRACT(HOUR FROM CAST({args[0]} AS TIMESTAMP)) AS DOUBLE)"
			if fn == "day_of_week" and len(args) == 1:
				# 0 = Monday .. 6 = Sunday (matches pandas dt.dayofweek)
				return f"CAST(EXTRACT(ISODOW FROM _ts) - 1 AS DOUBLE)" if args[0] == '"timestamp"' else f"CAST(EXTRACT(ISODOW FROM CAST({args[0]} AS TIMESTAMP)) - 1 AS DOUBLE)"
			if fn == "if_else" and len(args) == 3:
				return f"(CASE WHEN {args[0]} THEN {args[1]} ELSE {args[2]} END)"
			if fn == "lower" and len(args) == 1:
				return f"LOWER(CAST({args[0]} AS VARCHAR))"
			if fn == "upper" and len(args) == 1:
				return f"UPPER(CAST({args[0]} AS VARCHAR))"
			if fn == "len" and len(args) == 1:
				return f"CAST(LENGTH(CAST({args[0]} AS VARCHAR)) AS DOUBLE)"
			raise ValueError(f"Hàm '{fn}' không nằm trong whitelist cho phép của EXPRESSION.")

		raise ValueError(f"Cấu trúc '{type(node).__name__}' không được phép trong biểu thức EXPRESSION.")

	sql_expr = _compile(tree)
	referenced = {r for r in referenced if r.lower() not in _RESERVED_SQL_NAMES}
	return sql_expr, referenced


__all__ = ["parse_safe_expression"]

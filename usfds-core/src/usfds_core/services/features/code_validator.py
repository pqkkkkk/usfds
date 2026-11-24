"""AST security validator for user/dynamic PYTHON_CODE feature scripts."""
import ast
import hashlib
import os
from typing import Iterable, Optional, Set


DEFAULT_ALLOWED_IMPORTS: Set[str] = {
	"math",
	"re",
	"ipaddress",
	"hashlib",
	"datetime",
	"collections",
	"itertools",
	"functools",
	"statistics",
	"json",
	"numpy",
	"pandas",
}

_FORBIDDEN_IMPORTS: Set[str] = {
	"os",
	"sys",
	"subprocess",
	"socket",
	"pathlib",
	"shutil",
	"ctypes",
	"importlib",
	"builtins",
	"pickle",
	"marshal",
	"urllib",
	"http",
	"requests",
	"multiprocessing",
	"threading",
	"pty",
	"signal",
}

_FORBIDDEN_CALLS: Set[str] = {
	"eval",
	"exec",
	"compile",
	"__import__",
	"open",
	"input",
	"getattr",
	"setattr",
	"delattr",
	"globals",
	"locals",
	"vars",
	"breakpoint",
	"dir",
}


def get_allowed_imports(override: Optional[Iterable[str]] = None) -> Set[str]:
	"""Returns the configured import allowlist (explicit override > env > default)."""
	if override is not None:
		return {str(x).strip().split(".")[0] for x in override if str(x).strip()}
	env_val = os.getenv("USFDS_FEATURE_ALLOWED_IMPORTS", "").strip()
	if env_val:
		return {x.strip().split(".")[0] for x in env_val.split(",") if x.strip()}
	return set(DEFAULT_ALLOWED_IMPORTS)


def compute_code_sha256(source_code: Optional[str]) -> Optional[str]:
	"""Computes SHA-256 hex digest of source code for snapshot lineage."""
	if source_code is None:
		return None
	return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def validate_feature_code(
	source_code: Optional[str],
	is_stateful: bool = False,
	allowed_imports: Optional[Iterable[str]] = None,
	max_bytes: int = 65536,
	required_packages: Optional[Iterable[str]] = None,
) -> None:
	"""Validates dynamic PYTHON_CODE source strictly against the AST security whitelist.

	Raises ValueError describing every security or contract violation found.
	"""
	if not isinstance(source_code, str) or not source_code.strip():
		raise ValueError("Mã nguồn (source_code) cho đặc trưng PYTHON_CODE không được để trống.")

	encoded_len = len(source_code.encode("utf-8"))
	if encoded_len > max_bytes:
		raise ValueError(
			f"Kích thước mã nguồn ({encoded_len} bytes) vượt quá giới hạn cho phép ({max_bytes} bytes)."
		)

	allow = get_allowed_imports(allowed_imports)

	for pkg in (required_packages or []):
		top_pkg = str(pkg).strip().split(".")[0]
		if not top_pkg:
			continue
		if top_pkg not in allow or top_pkg in _FORBIDDEN_IMPORTS:
			raise ValueError(
				f"Thư viện yêu cầu '{pkg}' không nằm trong danh sách import được phép (USFDS_FEATURE_ALLOWED_IMPORTS)."
			)

	try:
		tree = ast.parse(source_code)
	except SyntaxError as exc:
		raise ValueError(f"Lỗi cú pháp Python tại dòng {exc.lineno}: {exc.msg}.") from exc

	top_level_funcs: dict[str, ast.FunctionDef] = {}
	for node in tree.body:
		if isinstance(node, ast.FunctionDef):
			top_level_funcs[node.name] = node

	if "compute" not in top_level_funcs:
		raise ValueError("Mã nguồn PYTHON_CODE bắt buộc phải định nghĩa hàm `def compute(...)`.")

	compute_fn = top_level_funcs["compute"]
	compute_arg_count = len(compute_fn.args.args)
	if is_stateful:
		if "fit" not in top_level_funcs:
			raise ValueError("Đặc trưng stateful (`is_stateful=True`) bắt buộc phải định nghĩa hàm `def fit(train_df, params)`.")
		if len(top_level_funcs["fit"].args.args) < 2:
			raise ValueError("Hàm `fit(train_df, params)` phải nhận ít nhất 2 tham số.")
		if compute_arg_count < 3:
			raise ValueError("Hàm `compute(df, params, state)` với đặc trưng stateful phải nhận 3 tham số.")
	else:
		if compute_arg_count < 2:
			raise ValueError("Hàm `compute(df, params)` phải nhận 2 tham số.")

	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for alias in node.names:
				top = alias.name.split(".")[0]
				if top in _FORBIDDEN_IMPORTS or top not in allow:
					raise ValueError(f"Import '{alias.name}' bị cấm bởi chính sách an toàn của USFDS.")
		elif isinstance(node, ast.ImportFrom):
			mod = (node.module or "").split(".")[0]
			if not mod or mod in _FORBIDDEN_IMPORTS or mod not in allow:
				raise ValueError(f"Import từ '{node.module}' bị cấm bởi chính sách an toàn của USFDS.")
		elif isinstance(node, ast.Call):
			if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
				raise ValueError(f"Lệnh gọi hàm '{node.func.id}()' bị cấm trong mã đặc trưng.")
		elif isinstance(node, ast.Attribute):
			if node.attr.startswith("__") and node.attr.endswith("__"):
				raise ValueError(f"Truy cập thuộc tính nội bộ '{node.attr}' bị cấm trong mã đặc trưng.")
		elif isinstance(node, ast.Name):
			if node.id in ("__builtins__", "__loader__", "__spec__"):
				raise ValueError(f"Truy cập định danh hệ thống '{node.id}' bị cấm trong mã đặc trưng.")


__all__ = [
	"DEFAULT_ALLOWED_IMPORTS",
	"compute_code_sha256",
	"get_allowed_imports",
	"validate_feature_code",
]

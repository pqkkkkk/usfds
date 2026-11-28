"""Automated API security & Clean Architecture boundary guards for usfds-server (INV-001, INV-002, INV-005)."""
import ast
from pathlib import Path
from typing import Iterable

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from usfds_server.api import app, build_cors_options

SERVER_ROUTERS_DIR = Path(__file__).resolve().parents[1] / "src" / "usfds_server" / "routers"

# INV-001: Exhaustive allowlist of intentionally unauthenticated endpoints.
# Adding a new public endpoint requires explicit review and updating this allowlist.
PUBLIC_ROUTES_ALLOWLIST: frozenset[tuple[str, str]] = frozenset({
	("GET", "/health"),
	("GET", "/api/health"),
	("GET", "/api/v1/auth/mode"),
	("POST", "/api/v1/auth/login"),
	("POST", "/api/v1/auth/refresh"),
	("POST", "/api/v1/auth/logout"),
})

# FastAPI built-in documentation/schema endpoints.
FRAMEWORK_DOC_PATHS: frozenset[str] = frozenset({
	"/openapi.json",
	"/docs",
	"/docs/oauth2-redirect",
	"/redoc",
})

# Routes that intentionally manage short-lived DB sessions manually (INV-008: 3-phase DB hygiene
# around network I/O) instead of FastAPI Depends(get_db)->Depends(get_actor_context).
# Every entry here is still verified live below to reject unauthenticated calls with HTTP 401.
MANUAL_SESSION_AUTH_ALLOWLIST: frozenset[tuple[str, str]] = frozenset({
	("GET", "/api/v1/training/runs/{run_id}"),
})

# Accepted auth dependency callable names in FastAPI route dependency trees.
AUTH_DEPENDENCY_NAMES: frozenset[str] = frozenset({
	"get_actor_context",
	"get_current_user",
	"_dependency",  # closure returned by require_system_permission(...)
})

# Prefixes where every route belongs to project-scoped domain resources (INV-002).
PROJECT_SCOPED_PREFIXES: tuple[str, ...] = (
	"/api/v1/datasets",
	"/api/v1/features",
	"/api/v1/feature-sets",
	"/api/v1/training",
	"/api/v1/rules",
	"/api/v1/detection",
	"/api/v1/cases",
	"/api/v1/blacklist",
	"/api/v1/network",
	"/api/v1/reports",
)


def _iter_dependant_call_names(dependant: Dependant) -> Iterable[str]:
	if dependant.call is not None:
		name = getattr(dependant.call, "__name__", None)
		if name:
			yield name
	for child in dependant.dependencies:
		yield from _iter_dependant_call_names(child)


def test_all_non_public_routes_enforce_authentication():
	"""INV-001: Every FastAPI route outside PUBLIC_ROUTES_ALLOWLIST must declare an auth dependency."""
	unprotected: list[str] = []
	for route in app.routes:
		if not isinstance(route, APIRoute):
			continue
		if route.path in FRAMEWORK_DOC_PATHS:
			continue
		dep_names = set(_iter_dependant_call_names(route.dependant))
		has_auth = bool(dep_names & AUTH_DEPENDENCY_NAMES)
		for method in sorted(route.methods or ()):
			if method in {"HEAD", "OPTIONS"}:
				continue
			if (method, route.path) in PUBLIC_ROUTES_ALLOWLIST:
				continue
			if (method, route.path) in MANUAL_SESSION_AUTH_ALLOWLIST:
				continue
			if not has_auth:
				unprotected.append(f"{method} {route.path} (deps={sorted(dep_names)})")

	assert not unprotected, (
		"Unauthenticated API route(s) detected outside PUBLIC_ROUTES_ALLOWLIST (INV-001):\n"
		+ "\n".join(unprotected)
	)


def test_public_and_manual_auth_allowlists_have_no_stale_entries():
	"""Keep PUBLIC_ROUTES_ALLOWLIST and MANUAL_SESSION_AUTH_ALLOWLIST strictly synchronized with registered routes."""
	registered = {
		(method, route.path)
		for route in app.routes
		if isinstance(route, APIRoute)
		for method in (route.methods or ())
	}
	stale_public = sorted(PUBLIC_ROUTES_ALLOWLIST - registered)
	stale_manual = sorted(MANUAL_SESSION_AUTH_ALLOWLIST - registered)
	assert not stale_public, f"Stale entries in PUBLIC_ROUTES_ALLOWLIST: {stale_public}"
	assert not stale_manual, f"Stale entries in MANUAL_SESSION_AUTH_ALLOWLIST: {stale_manual}"


def test_manual_session_auth_routes_reject_unauthenticated_requests(monkeypatch, client, server_settings):
	"""INV-001 / INV-008: Routes using manual short-lived auth sessions must still reject missing JWT with 401."""
	from uuid import uuid4

	monkeypatch.setattr(server_settings, "auth_mode", "required")
	resp = client.get(f"/api/v1/training/runs/{uuid4()}", params={"project_id": str(uuid4())})
	assert resp.status_code == 401


def test_project_scoped_routes_always_resolve_actor_context():
	"""INV-002: All project-scoped domain routes must require ActorContext (not just bare user token)."""
	violations: list[str] = []
	for route in app.routes:
		if not isinstance(route, APIRoute):
			continue
		if not route.path.startswith(PROJECT_SCOPED_PREFIXES):
			continue
		dep_names = set(_iter_dependant_call_names(route.dependant))
		if "get_actor_context" not in dep_names:
			for method in sorted(route.methods or ()):
				if method in {"HEAD", "OPTIONS"} or (method, route.path) in MANUAL_SESSION_AUTH_ALLOWLIST:
					continue
				violations.append(f"{method} {route.path} missing get_actor_context")

	assert not violations, (
		"Project-scoped route(s) missing ActorContext enforcement (INV-002):\n"
		+ "\n".join(violations)
	)


def test_cors_disables_credentials_on_wildcard():
	"""INV-001 / ISS-014: Wildcard '*' CORS origin must never enable allow_credentials."""
	assert build_cors_options("*") == (["*"], False)
	assert build_cors_options("http://localhost:5173, *") == (["*"], False)
	assert build_cors_options("") == (["*"], False)
	assert build_cors_options("http://localhost:5173,https://app.example.com") == (
		["http://localhost:5173", "https://app.example.com"],
		True,
	)


def test_server_routers_do_not_import_orm_models_directly():
	"""INV-005: FastAPI routers must interact with persistence through providers/services, never ORM tables directly."""
	forbidden_prefixes = (
		"usfds_infra.database.models",
		"usfds_infra.database.tables",
		"usfds_infra.database.case_models",
	)
	violations: list[str] = []
	for py_file in sorted(SERVER_ROUTERS_DIR.rglob("*.py")):
		if "__pycache__" in py_file.parts:
			continue
		tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
		for node in ast.walk(tree):
			modules: list[str] = []
			if isinstance(node, ast.Import):
				modules = [alias.name for alias in node.names]
			elif isinstance(node, ast.ImportFrom) and node.module:
				modules = [node.module]
			for mod in modules:
				if any(mod == pref or mod.startswith(f"{pref}.") for pref in forbidden_prefixes):
					violations.append(f"{py_file.name}:{node.lineno} imports ORM module '{mod}'")

	assert not violations, "Router ORM boundary violation(s) (INV-005):\n" + "\n".join(violations)

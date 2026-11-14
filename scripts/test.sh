#!/usr/bin/env bash
# Single test entrypoint for humans and agents. No Docker required.
#   ./scripts/test.sh                 # all packages
#   ./scripts/test.sh core server     # selected packages
#   ./scripts/test.sh server -- -k delete   # extra args after `--` go to pytest / npm test
# Packages: core infra server worker cli web
# Python envs are pinned to 3.12 (see .plan/parallel_agent_setup.md §6) and created on first use.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_VERSION="3.12"
ALL_PACKAGES=(core infra server worker cli web)

packages=()
extra_args=()
while [[ $# -gt 0 ]]; do
	if [[ "$1" == "--" ]]; then
		shift
		extra_args=("$@")
		break
	fi
	packages+=("$1")
	shift
done
if [[ ${#packages[@]} -eq 0 || "${packages[0]}" == "all" ]]; then
	packages=("${ALL_PACKAGES[@]}")
fi

# Tests must never pick up deployment settings from the developer's shell.
for var in $(env | grep -o '^USFDS_[A-Z0-9_]*' || true); do
	unset "$var"
done

_python_bin() {
	if command -v uv >/dev/null 2>&1; then
		uv python find "$PY_VERSION" 2>/dev/null && return 0
	fi
	command -v "python$PY_VERSION" 2>/dev/null && return 0
	echo "Python $PY_VERSION not found. Install it with: uv python install $PY_VERSION" >&2
	return 1
}

_ensure_python_env() {
	local dir="$1"
	local current
	current="$(cd "$dir" && poetry run python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || true)"
	if [[ "$current" != "$PY_VERSION" ]]; then
		local py
		py="$(_python_bin)" || return 1
		(cd "$dir" && poetry env use "$py" >/dev/null) || return 1
	fi
	# Re-install whenever the lock or pyproject changed since the last install.
	local venv lock_hash marker
	venv="$(cd "$dir" && poetry env info -p)" || return 1
	lock_hash="$(cat "$dir/poetry.lock" "$dir/pyproject.toml" | shasum | cut -d' ' -f1)"
	marker="$venv/.usfds-lock-hash"
	if [[ ! -f "$marker" || "$(cat "$marker")" != "$lock_hash" ]]; then
		echo "Installing dependencies for $(basename "$dir") ..."
		(cd "$dir" && poetry sync --no-interaction >/dev/null) || return 1
		echo "$lock_hash" > "$marker"
	fi
}

_run_python_package() {
	local dir="$ROOT/usfds-$1"
	_ensure_python_env "$dir" || return 1
	(cd "$dir" && poetry run pytest -q -p no:cacheprovider ${extra_args[@]+"${extra_args[@]}"})
}

_run_web() {
	local dir="$ROOT/usfds-web"
	if [[ ! -d "$dir/node_modules" ]]; then
		(cd "$dir" && npm ci --no-audit --no-fund >/dev/null) || return 1
	fi
	if (cd "$dir" && node -e 'process.exit(require("./package.json").scripts?.test ? 0 : 1)'); then
		(cd "$dir" && npm test -- ${extra_args[@]+"${extra_args[@]}"})
	else
		(cd "$dir" && node --test tests/*.mjs)
	fi
}

declare -a results=()
status=0
for pkg in "${packages[@]}"; do
	echo "===== $pkg ====="
	case "$pkg" in
		web) _run_web ;;
		core|infra|server|worker|cli) _run_python_package "$pkg" ;;
		*) echo "Unknown package: $pkg" >&2; false ;;
	esac
	code=$?
	if [[ $code -eq 0 ]]; then
		results+=("PASS  $pkg")
	else
		results+=("FAIL  $pkg (exit $code)")
		status=1
	fi
done

echo
echo "===== summary ====="
printf '%s\n' "${results[@]}"
exit $status

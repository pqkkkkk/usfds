"""Isolated batched subprocess runner for Tier 2 PYTHON_CODE features."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from usfds_core.domain.entities.feature import Feature
from usfds_core.services.features.code_validator import validate_feature_code


class FeatureExecutionError(RuntimeError):
	"""Raised when a dynamic PYTHON_CODE feature fails validation, shape checks, or runtime."""


_SUBPROCESS_RUNNER_CODE = '''"""Auto-generated isolated runner for batched PYTHON_CODE features."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback
import pandas as pd


def _coerce_series(raw, expected_len: int, index, output_type: str, feature_key: str) -> pd.Series:
	if isinstance(raw, pd.Series):
		if len(raw) != expected_len:
			raise ValueError(f"Series length {len(raw)} != expected {expected_len}")
		s = pd.Series(raw.to_numpy(), index=index)
	elif isinstance(raw, (list, tuple)) or hasattr(raw, "__len__") and not isinstance(raw, (str, bytes, dict)):
		if len(raw) != expected_len:
			raise ValueError(f"Sequence length {len(raw)} != expected {expected_len}")
		s = pd.Series(list(raw), index=index)
	else:
		raise TypeError(f"compute() for '{feature_key}' must return a pd.Series or 1D sequence of length {expected_len}, got {type(raw).__name__}")

	if output_type == "NUMERIC":
		return pd.to_numeric(s, errors="coerce").astype("float64")
	if output_type == "BOOLEAN":
		return s.fillna(False).astype(bool)
	return s.fillna("").astype(str).astype(object)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--mode", choices=["fit_transform", "transform"], required=True)
	parser.add_argument("--manifest", required=True)
	parser.add_argument("--input-parquet", required=True)
	parser.add_argument("--output-parquet", required=True)
	parser.add_argument("--states-in", required=False)
	parser.add_argument("--states-out", required=True)
	args = parser.parse_args()

	with open(args.manifest, "r", encoding="utf-8") as mf:
		specs = json.load(mf)

	existing_states = {}
	if args.states_in and Path(args.states_in).exists():
		with open(args.states_in, "r", encoding="utf-8") as sf:
			existing_states = json.load(sf)

	df = pd.read_parquet(args.input_parquet)
	out_df = pd.DataFrame({"_row_idx": df["_row_idx"] if "_row_idx" in df.columns else range(len(df))}, index=df.index)
	new_states = {}

	for spec in specs:
		fkey = spec["feature_key"]
		is_stateful = bool(spec.get("is_stateful", False))
		output_type = str(spec.get("output_type", "NUMERIC"))
		config_json = spec.get("config_json") or {}
		params = config_json.get("params") if isinstance(config_json.get("params"), dict) else dict(config_json)
		code = spec["source_code"]

		namespace = {}
		try:
			exec(compile(code, f"<feature:{fkey}>", "exec"), namespace)
			if is_stateful:
				if args.mode == "fit_transform":
					state = namespace["fit"](df, params)
					if not isinstance(state, dict):
						raise TypeError(f"fit() for '{fkey}' must return a JSON-serializable dict, got {type(state).__name__}")
					json.dumps(state)
					new_states[fkey] = state
				else:
					state = existing_states.get(fkey, {})
					new_states[fkey] = state
				raw_res = namespace["compute"](df, params, state)
			else:
				raw_res = namespace["compute"](df, params)
			out_df[fkey] = _coerce_series(raw_res, len(df), df.index, output_type, fkey)
		except Exception as exc:
			tb = traceback.format_exc()
			sys.stderr.write(f"FEATURE_ERROR[{fkey}]: {exc}\\n{tb}")
			sys.exit(2)

	out_df.to_parquet(args.output_parquet, index=False)
	with open(args.states_out, "w", encoding="utf-8") as sf:
		json.dump(new_states, sf)


if __name__ == "__main__":
	main()
'''


class BatchedFeatureScriptRunner:
	"""Runs a batch of same-level PYTHON_CODE features in one isolated subprocess."""

	def __init__(
		self,
		timeout_seconds: int = 60,
		max_bytes: int = 65536,
		allowed_imports: Optional[Iterable[str]] = None,
	) -> None:
		self.timeout_seconds = max(1, int(timeout_seconds))
		self.max_bytes = int(max_bytes)
		self.allowed_imports = list(allowed_imports) if allowed_imports is not None else None

	def run_level(
		self,
		df: pd.DataFrame,
		features: List[Feature],
		mode: str = "fit_transform",
		states_in: Optional[Dict[str, Dict[str, Any]]] = None,
	) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
		"""Re-validates AST for every feature and runs them batched in a subprocess."""
		if not features:
			empty_out = pd.DataFrame({"_row_idx": df["_row_idx"] if "_row_idx" in df.columns else range(len(df))}, index=df.index)
			return empty_out, {}

		manifest: List[Dict[str, Any]] = []
		for feat in features:
			config_json = dict(feat.config_json or {})
			validate_feature_code(
				feat.source_code,
				is_stateful=feat.is_stateful,
				allowed_imports=self.allowed_imports,
				max_bytes=self.max_bytes,
				required_packages=config_json.get("required_packages"),
			)
			manifest.append(
				{
					"feature_key": feat.feature_key,
					"is_stateful": bool(feat.is_stateful),
					"output_type": feat.output_type.value if hasattr(feat.output_type, "value") else str(feat.output_type),
					"config_json": config_json,
					"source_code": feat.source_code,
				}
			)

		with tempfile.TemporaryDirectory(prefix="usfds_feat_batch_") as tmp_dir:
			tmp_path = Path(tmp_dir)
			runner_path = tmp_path / "_feature_runner.py"
			manifest_path = tmp_path / "manifest.json"
			input_parquet = tmp_path / "input.parquet"
			output_parquet = tmp_path / "output.parquet"
			states_in_path = tmp_path / "states_in.json"
			states_out_path = tmp_path / "states_out.json"

			runner_path.write_text(_SUBPROCESS_RUNNER_CODE, encoding="utf-8")
			manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
			df.to_parquet(input_parquet, index=False)

			cmd = [
				sys.executable,
				str(runner_path),
				"--mode",
				mode,
				"--manifest",
				str(manifest_path),
				"--input-parquet",
				str(input_parquet),
				"--output-parquet",
				str(output_parquet),
				"--states-out",
				str(states_out_path),
			]
			if states_in is not None:
				states_in_path.write_text(json.dumps(states_in), encoding="utf-8")
				cmd.extend(["--states-in", str(states_in_path)])

			try:
				proc = subprocess.run(
					cmd,
					capture_output=True,
					text=True,
					timeout=self.timeout_seconds,
					check=False,
				)
			except subprocess.TimeoutExpired as exc:
				raise TimeoutError(
					f"Thực thi PYTHON_CODE feature quá thời gian ({self.timeout_seconds}s)."
				) from exc

			if proc.returncode != 0:
				detail = (proc.stderr or proc.stdout or "").strip()
				raise FeatureExecutionError(f"Lỗi thực thi PYTHON_CODE feature: {detail}")

			out_df = pd.read_parquet(output_parquet)
			new_states: Dict[str, Dict[str, Any]] = {}
			if states_out_path.exists():
				new_states = json.loads(states_out_path.read_text(encoding="utf-8"))
			return out_df, new_states


__all__ = ["BatchedFeatureScriptRunner", "FeatureExecutionError"]

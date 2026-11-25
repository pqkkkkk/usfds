"""Shared bounded DuckDB I/O, hashing, and type-mapping helpers for Data Management (ISS-044)."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import duckdb

from usfds_core.domain.entities.enums import LogicalDataType
from usfds_core.services.warehouse.project_warehouse import create_bounded_duckdb_connection

_NUMERIC_EXACT_TYPES = {
	"TINYINT",
	"SMALLINT",
	"INTEGER",
	"INT",
	"INT1",
	"INT2",
	"INT4",
	"INT8",
	"BIGINT",
	"HUGEINT",
	"UTINYINT",
	"USMALLINT",
	"UINTEGER",
	"UBIGINT",
	"UHUGEINT",
	"FLOAT",
	"FLOAT4",
	"FLOAT8",
	"DOUBLE",
	"REAL",
}

_INT_EXACT_TYPES = {
	"TINYINT",
	"SMALLINT",
	"INTEGER",
	"INT",
	"INT1",
	"INT2",
	"INT4",
	"INT8",
	"BIGINT",
	"HUGEINT",
	"UTINYINT",
	"USMALLINT",
	"UINTEGER",
	"UBIGINT",
	"UHUGEINT",
}

_STRING_PREFIXES = ("VARCHAR", "TEXT", "CHAR", "STRING", "UUID")


def quote_ident(name: str) -> str:
	"""Quote a SQL identifier for DuckDB."""
	return '"' + str(name).replace('"', '""') + '"'


def quote_literal(value: str) -> str:
	"""Quote a SQL string literal for DuckDB."""
	return "'" + str(value).replace("'", "''") + "'"


def create_utc_bounded_duckdb_connection(
	threads: int = 2,
	memory_limit: str = "512MB",
	temp_directory: Optional[str] = None,
) -> duckdb.DuckDBPyConnection:
	"""Create a bounded DuckDB connection pinned to UTC timezone."""
	conn = create_bounded_duckdb_connection(
		threads=threads,
		memory_limit=memory_limit,
		temp_directory=temp_directory,
	)
	conn.execute("SET TimeZone = 'UTC'")
	return conn


def sha256_file(local_path: Union[str, Path], chunk_size: int = 1024 * 1024) -> str:
	"""Compute SHA-256 hex digest of a file using streaming chunks."""
	digest = hashlib.sha256()
	with open(local_path, "rb") as f:
		while True:
			chunk = f.read(chunk_size)
			if not chunk:
				break
			digest.update(chunk)
	return digest.hexdigest()


def duckdb_type_to_logical_type(duckdb_type: str) -> LogicalDataType:
	"""Map a DuckDB column type name to a USFDS LogicalDataType."""
	upper = str(duckdb_type).strip().upper()
	if upper in ("BOOLEAN", "BOOL"):
		return LogicalDataType.BOOLEAN
	if upper.startswith("TIMESTAMP") or upper == "DATE":
		return LogicalDataType.DATETIME
	if upper in _NUMERIC_EXACT_TYPES or upper.startswith(("DECIMAL", "NUMERIC")):
		return LogicalDataType.NUMERIC
	return LogicalDataType.STRING


def duckdb_type_to_physical_dtype(duckdb_type: str) -> str:
	"""Map a DuckDB column type name to a pandas-compatible physical dtype string."""
	upper = str(duckdb_type).strip().upper()
	if upper in ("BOOLEAN", "BOOL"):
		return "bool"
	if upper.startswith("TIMESTAMP") or upper == "DATE":
		return "datetime64[ns]"
	if upper in _INT_EXACT_TYPES:
		return "int64"
	if upper in ("FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL") or upper.startswith(("DECIMAL", "NUMERIC")):
		return "float64"
	return "object"


def is_duckdb_string_type(duckdb_type: str) -> bool:
	"""Return True if the DuckDB type represents character/string data."""
	return str(duckdb_type).strip().upper().startswith(_STRING_PREFIXES)


def is_duckdb_numeric_type(duckdb_type: str) -> bool:
	"""Return True if the DuckDB type represents numeric data."""
	return duckdb_type_to_logical_type(duckdb_type) == LogicalDataType.NUMERIC


def is_duckdb_datetime_type(duckdb_type: str) -> bool:
	"""Return True if the DuckDB type represents date/timestamp data."""
	return duckdb_type_to_logical_type(duckdb_type) == LogicalDataType.DATETIME


def register_file_view(
	conn: duckdb.DuckDBPyConnection,
	local_path: Union[str, Path],
	view_name: str = "src",
	source_hint: Optional[str] = None,
) -> Tuple[List[str], Dict[str, str]]:
	"""Register a local CSV/Parquet/JSON file as a DuckDB view and return (columns, type_map)."""
	path = Path(local_path)
	hint = source_hint or str(local_path)
	lower = hint.lower()
	path_lit = quote_literal(path.as_posix())
	view_ident = quote_ident(view_name)

	try:
		if lower.endswith((".parquet", ".pq")):
			conn.execute(f"CREATE OR REPLACE VIEW {view_ident} AS SELECT * FROM read_parquet({path_lit})")
		elif lower.endswith((".csv", ".txt")):
			conn.execute(
				f"CREATE OR REPLACE VIEW {view_ident} AS SELECT * FROM read_csv_auto({path_lit}, sample_size=20480)"
			)
		elif lower.endswith(".json"):
			conn.execute(f"CREATE OR REPLACE VIEW {view_ident} AS SELECT * FROM read_json_auto({path_lit})")
		else:
			try:
				conn.execute(f"CREATE OR REPLACE VIEW {view_ident} AS SELECT * FROM read_parquet({path_lit})")
			except Exception:
				conn.execute(
					f"CREATE OR REPLACE VIEW {view_ident} AS SELECT * FROM read_csv_auto({path_lit}, sample_size=20480)"
				)
		described = conn.execute(f"DESCRIBE SELECT * FROM {view_ident}").fetchall()
	except Exception as err:
		raise ValueError(f"Failed to parse tabular data from '{hint}': {err}") from err

	columns = [str(row[0]) for row in described]
	types = {str(row[0]): str(row[1]) for row in described}
	return columns, types


def copy_query_to_file(
	conn: duckdb.DuckDBPyConnection,
	select_sql: str,
	dest_path: Union[str, Path],
	ext: str,
) -> None:
	"""Materialize a DuckDB SELECT query directly to disk in Parquet, JSON, or CSV format."""
	dest_lit = quote_literal(Path(dest_path).as_posix())
	ext_low = ext.lower()
	if ext_low in (".parquet", ".pq"):
		conn.execute(f"COPY ({select_sql}) TO {dest_lit} (FORMAT PARQUET)")
	elif ext_low == ".json":
		conn.execute(f"COPY ({select_sql}) TO {dest_lit} (FORMAT JSON, ARRAY true)")
	else:
		conn.execute(f"COPY ({select_sql}) TO {dest_lit} (FORMAT CSV, HEADER true)")


__all__ = [
	"copy_query_to_file",
	"create_utc_bounded_duckdb_connection",
	"duckdb_type_to_logical_type",
	"duckdb_type_to_physical_dtype",
	"is_duckdb_datetime_type",
	"is_duckdb_numeric_type",
	"is_duckdb_string_type",
	"quote_ident",
	"quote_literal",
	"register_file_view",
	"sha256_file",
]

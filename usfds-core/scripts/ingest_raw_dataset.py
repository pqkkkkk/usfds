#!/usr/bin/env python3
"""Script to ingest a raw dataset file, execute basic EDA, and export EDA summary to JSON.

Usage:
    python scripts/ingest_raw_dataset.py --input-file <path_to_file> [--output-json <path_to_json>]
    python scripts/ingest_raw_dataset.py -i ../datasets/e-commerce-fraud-detection-dataset/raw.csv -o eda_summary.json
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Union
from uuid import UUID, uuid4

# Ensure usfds_core package is accessible from python path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from usfds_core.repositories.in_memory_repos import InMemoryDatasetArtifactRepository
from usfds_core.services.eda.raw_ingestion_service import RawDatasetIngestionService
from usfds_core.storage.base_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """Local filesystem implementation of IFileStorage for CLI and local scripts."""

    def __init__(self, base_dir: Union[str, Path] = "."):
        self.base_dir = Path(base_dir).resolve()

    def _resolve_path(self, file_path: str) -> Path:
        p = Path(file_path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    def save_bytes(self, file_path: str, data: bytes) -> str:
        target = self._resolve_path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, file_path: str) -> bytes:
        target = self._resolve_path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found in local storage: {target}")
        return target.read_bytes()

    def exists(self, file_path: str) -> bool:
        target = self._resolve_path(file_path)
        return target.is_file()


def run_ingest_and_eda(
    input_file_path: Union[str, Path],
    output_json_path: Optional[Union[str, Path]] = None,
    dataset_id: Optional[UUID] = None,
    user_name: str = "system",
) -> Path:
    """Ingests a raw dataset using RawDatasetIngestionService and saves the EDA summary to JSON."""
    input_path = Path(input_file_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input dataset file does not exist: {input_path}")

    # Determine output JSON path
    if output_json_path is not None:
        out_path = Path(output_json_path).resolve()
    else:
        out_path = input_path.parent / f"{input_path.stem}_eda_summary.json"

    ds_id = dataset_id or uuid4()

    # Initialize storage and repository
    storage = LocalFileStorage(base_dir=input_path.parent)
    repo = InMemoryDatasetArtifactRepository()

    # Initialize RawDatasetIngestionService
    service = RawDatasetIngestionService(
        file_storage=storage,
        artifact_repo=repo,
    )

    print(f"[*] Ingesting raw dataset from: {input_path}")
    print(f"    - Dataset ID: {ds_id}")
    print(f"    - User:       {user_name}")

    # Ingest raw dataset (PipelineStage.RAW)
    artifact = service.ingest_raw_dataset(
        dataset_id=ds_id,
        storage_path=str(input_path),
        user_name=user_name,
    )

    print(f"[+] Raw Dataset Artifact Created:")
    print(f"    - Artifact ID:      {artifact.artifact_id}")
    print(f"    - Pipeline Stage:   {artifact.pipeline_stage}")
    print(f"    - SHA-256 Checksum: {artifact.checksum_sha256}")
    print(f"    - Row Count:        {artifact.row_count:,}")
    print(f"    - Column Count:     {artifact.column_count}")
    print(f"    - Validation Status:{artifact.validation_status}")

    # Extract EDA summary
    eda_summary = artifact.validation_report.get("eda")
    if not eda_summary:
        raise ValueError("EDA summary was not generated in the artifact validation report.")

    # Save to JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eda_summary, f, indent=2)

    print(f"[+] Successfully saved EDA summary JSON to: {out_path}")

    # Print summary table preview
    print("\n--- EDA Field Summary Preview ---")
    print(f"{'Field Name':<25} {'Dtype':<12} {'Unique':<10} {'Nulls':<10} {'Null %':<8}")
    print("-" * 68)
    for field in eda_summary.get("fields", [])[:15]:
        print(
            f"{field['name']:<25} {field['dtype']:<12} {field['unique_count']:<10} "
            f"{field['null_count']:<10} {field['null_percentage']:<8.2f}%"
        )
    if len(eda_summary.get("fields", [])) > 15:
        print(f"... and {len(eda_summary['fields']) - 15} more fields.")
    print("-" * 68)

    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a raw dataset file and export basic EDA summary to JSON."
    )
    parser.add_argument(
        "-i",
        "--input-file",
        required=True,
        help="Path to the local dataset file (.csv, .parquet, .json).",
    )
    parser.add_argument(
        "-o",
        "--output-json",
        default=None,
        help="Path to save the output EDA JSON file (optional).",
    )
    parser.add_argument(
        "-d",
        "--dataset-id",
        default=None,
        help="Optional UUID for the dataset (default: auto-generated).",
    )
    parser.add_argument(
        "-u",
        "--user-name",
        default="system",
        help="User triggering the ingestion (default: 'system').",
    )

    args = parser.parse_args()

    ds_uuid = UUID(args.dataset_id) if args.dataset_id else None
    run_ingest_and_eda(
        input_file_path=args.input_file,
        output_json_path=args.output_json,
        dataset_id=ds_uuid,
        user_name=args.user_name,
    )


if __name__ == "__main__":
    main()

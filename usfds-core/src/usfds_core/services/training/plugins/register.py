"""Service for uploading, validating, packaging, and registering custom Model Plugins."""

import io
import json
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Optional, Tuple, Union
from uuid import UUID, uuid4
import zipfile

from usfds_core.domain.entities.enums import ExecutionType
from usfds_core.domain.entities.model import Model
from usfds_core.domain.schemas.model_plugin import ModelPluginManifest, PluginValidationResult
from usfds_core.repositories.base_model_repo import IModelRepository
from usfds_core.services.training.plugins.runner_template import RUNNER_SCRIPT_FILENAME
from usfds_core.services.training.plugins.validator import ModelPluginValidator
from usfds_core.storage.base_storage import IFileStorage

logger = logging.getLogger(__name__)


def package_directory_to_zip_bytes(source_dir: Path) -> bytes:
    """Compress a directory into a clean in-memory ZIP archive (excluding __pycache__ and .venv)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_dir():
                continue
            rel_parts = file_path.relative_to(source_dir).parts
            if any(part in ("__pycache__", ".git", ".venv", "venv", ".pytest_cache") for part in rel_parts):
                continue
            if file_path.suffix == ".pyc" or file_path.name == RUNNER_SCRIPT_FILENAME:
                continue
            arcname = "/".join(rel_parts)
            zf.write(file_path, arcname=arcname)
    return buf.getvalue()


def extract_zip_bytes_to_directory(zip_bytes: bytes, target_dir: Path) -> Path:
    """Extract ZIP bytes into `target_dir`. If the archive has a single top-level directory, flatten it."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        zf.extractall(target_dir)

    entries = [p for p in target_dir.iterdir() if p.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir() and not (target_dir / "main.py").exists():
        nested_root = entries[0]
        for child in list(nested_root.iterdir()):
            shutil.move(str(child), str(target_dir / child.name))
        shutil.rmtree(nested_root, ignore_errors=True)

    return target_dir


def package_model_bundle_bytes(
    artifact_dir: Path,
    plugin_src_dir: Optional[Path] = None,
) -> bytes:
    """Package trained model + preprocessor artifacts (and optional plugin source code)
    into a self-contained `model_bundle.zip` archive for immutable ModelVersion storage.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if plugin_src_dir and plugin_src_dir.exists():
            for file_path in sorted(plugin_src_dir.rglob("*")):
                if file_path.is_dir():
                    continue
                rel_parts = file_path.relative_to(plugin_src_dir).parts
                if any(part in ("__pycache__", ".git", ".venv", "venv") for part in rel_parts):
                    continue
                if file_path.suffix == ".pyc":
                    continue
                arcname = "src/" + "/".join(rel_parts)
                zf.write(file_path, arcname=arcname)

        if artifact_dir.exists():
            for file_path in sorted(artifact_dir.rglob("*")):
                if file_path.is_dir():
                    continue
                rel_parts = file_path.relative_to(artifact_dir).parts
                arcname = "artifacts/" + "/".join(rel_parts)
                zf.write(file_path, arcname=arcname)

    return buf.getvalue()


class ModelPluginRegistrationService:
    """Orchestrates Step 1 -> Step 3 of the Model Plugin lifecycle:
    1. Receive user plugin source code (directory or zip archive).
    2. Validate via Static AST check + Dynamic Train & Inference Dry-Run.
    3. Persist source package to `IFileStorage` and save `Model` metadata to `IModelRepository`.
    """

    def __init__(
        self,
        model_repo: IModelRepository,
        file_storage: IFileStorage,
        validator: Optional[ModelPluginValidator] = None,
    ):
        self.model_repo = model_repo
        self.file_storage = file_storage
        self.validator = validator or ModelPluginValidator()

    def register_from_directory(
        self,
        plugin_dir: Union[str, Path],
        user_id: UUID,
        manifest_override: Optional[ModelPluginManifest] = None,
    ) -> Tuple[Optional[Model], PluginValidationResult]:
        """Validate a plugin directory and register it into the Model Registry if valid."""
        source_path = Path(plugin_dir).resolve()
        validation_res = self.validator.validate(source_path, manifest=manifest_override)
        if not validation_res.is_valid or validation_res.manifest is None:
            logger.warning(f"Plugin validation failed for {source_path}: {validation_res.errors}")
            return None, validation_res

        manifest = validation_res.manifest
        model_id = uuid4()

        # Ensure plugin_manifest.json is included inside the packaged zip
        temp_pkg_dir = Path(tempfile.mkdtemp(prefix="usfds_pkg_"))
        try:
            staging_dir = temp_pkg_dir / "plugin"
            shutil.copytree(source_path, staging_dir)
            with open(staging_dir / "plugin_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest.model_dump(mode="json"), f, indent=2)

            zip_bytes = package_directory_to_zip_bytes(staging_dir)
        finally:
            shutil.rmtree(temp_pkg_dir, ignore_errors=True)

        storage_uri = f"models/{model_id}/plugin_source.zip"
        self.file_storage.save_bytes(storage_uri, zip_bytes)

        model = Model(
            model_id=model_id,
            model_name=manifest.model_name,
            user_id=user_id,
            display_name=manifest.display_name or manifest.model_name,
            description=manifest.description,
            execution_type=ExecutionType.SCRIPT,
            entrypoint_uri=storage_uri,
            hyperparameter_schema=manifest.hyperparameter_schema,
            default_hyperparameters=manifest.default_hyperparameters,
        )
        self.model_repo.save(model)
        logger.info(
            f"Registered custom model plugin '{model.model_name}' (ID: {model.model_id}) at '{storage_uri}'."
        )
        return model, validation_res

    def register_from_zip(
        self,
        zip_bytes: bytes,
        user_id: UUID,
        manifest_override: Optional[ModelPluginManifest] = None,
    ) -> Tuple[Optional[Model], PluginValidationResult]:
        """Extract a ZIP archive of a user plugin, validate it, and register if valid."""
        temp_extract_dir = Path(tempfile.mkdtemp(prefix="usfds_zip_upload_"))
        try:
            extract_zip_bytes_to_directory(zip_bytes, temp_extract_dir)
            return self.register_from_directory(
                plugin_dir=temp_extract_dir,
                user_id=user_id,
                manifest_override=manifest_override,
            )
        finally:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

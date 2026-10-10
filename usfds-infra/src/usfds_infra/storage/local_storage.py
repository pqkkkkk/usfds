from pathlib import Path
import shutil
from typing import List, Union

from usfds_core.storage.base_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """Local filesystem implementation of IFileStorage with utilities for desktop ML pipelines."""

    def __init__(self, base_dir: Union[str, Path] = "."):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a relative or absolute path against base_dir.
        
        Relative paths are joined with base_dir. Absolute paths are returned as is.
        """
        p = Path(file_path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    def get_absolute_path(self, file_path: str) -> Path:
        """Get the absolute filesystem Path for a given relative or absolute file_path."""
        return self._resolve_path(file_path)

    def save_bytes(self, file_path: str, data: bytes) -> str:
        """Save a byte sequence to the target path and return the absolute path as string."""
        target = self._resolve_path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, file_path: str) -> bytes:
        """Read bytes from the given path."""
        target = self._resolve_path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found in local storage: {target}")
        return target.read_bytes()

    def exists(self, file_path: str) -> bool:
        """Check if a file exists at the given path."""
        target = self._resolve_path(file_path)
        return target.is_file()

    def delete(self, file_path: str) -> bool:
        """Delete a file if it exists. Returns True if deleted, False if not found."""
        target = self._resolve_path(file_path)
        if target.is_file():
            target.unlink()
            return True
        return False

    def save_file(self, src_path: Union[str, Path], dest_path: str) -> str:
        """Copy a file from an external path to local storage without loading into memory.
        
        Useful for large datasets (CSV, Parquet, PCAP) or model checkpoint weights (.pt, .onnx).
        """
        src = Path(src_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Source file does not exist: {src}")

        target = self._resolve_path(dest_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        return str(target)

    def get_file_size(self, file_path: str) -> int:
        """Return file size in bytes."""
        target = self._resolve_path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found in local storage: {target}")
        return target.stat().st_size

    def list_files(self, subdir: str = "") -> List[str]:
        """List relative paths of all files within a subdirectory of base_dir."""
        target_dir = self._resolve_path(subdir)
        if not target_dir.is_dir():
            return []

        relative_files: List[str] = []
        for file in target_dir.rglob("*"):
            if file.is_file():
                relative_files.append(str(file.relative_to(self.base_dir).as_posix()))
        return sorted(relative_files)


__all__ = ["LocalFileStorage"]

from pathlib import Path
from typing import Union

from usfds_core.storage.base_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """Local filesystem implementation of IFileStorage."""

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


__all__ = ["LocalFileStorage"]

from typing import Dict, List
from usfds_core.storage.base_storage import IFileStorage


class InMemoryFileStorage(IFileStorage):
    """In-memory implementation of IFileStorage for testing and isolated core services."""

    def __init__(self) -> None:
        self._storage: Dict[str, bytes] = {}

    def _normalize_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").strip("/")

    def save_bytes(self, file_path: str, data: bytes) -> str:
        """Saves bytes to the in-memory store under normalized path."""
        norm_path = self._normalize_path(file_path)
        self._storage[norm_path] = bytes(data)
        return file_path

    def read_bytes(self, file_path: str) -> bytes:
        """Reads bytes from the in-memory store. Raises FileNotFoundError if missing."""
        norm_path = self._normalize_path(file_path)
        if norm_path not in self._storage:
            raise FileNotFoundError(f"File '{file_path}' not found in in-memory storage.")
        return self._storage[norm_path]

    def exists(self, file_path: str) -> bool:
        """Checks if the given file exists in memory."""
        norm_path = self._normalize_path(file_path)
        return norm_path in self._storage

    def delete(self, file_path: str) -> bool:
        """Deletes a file from the in-memory storage if present."""
        norm_path = self._normalize_path(file_path)
        if norm_path in self._storage:
            del self._storage[norm_path]
            return True
        return False

    def list_files(self, prefix: str = "") -> List[str]:
        """Lists all stored file paths matching the optional prefix."""
        norm_prefix = self._normalize_path(prefix) if prefix else ""
        if not norm_prefix:
            return list(self._storage.keys())
        return [p for p in self._storage.keys() if p.startswith(norm_prefix)]

    def clear(self) -> None:
        """Clears all stored files."""
        self._storage.clear()


__all__ = ["InMemoryFileStorage"]

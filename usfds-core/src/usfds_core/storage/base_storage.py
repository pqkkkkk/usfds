from abc import ABC, abstractmethod
from typing import Optional


class IFileStorage(ABC):
    """Interface for abstract file and artifact storage within the Core layer."""

    @abstractmethod
    def save_bytes(self, file_path: str, data: bytes) -> str:
        """Save a byte sequence and return the storage path/URI."""
        pass

    @abstractmethod
    def read_bytes(self, file_path: str) -> bytes:
        """Read a byte sequence from the given storage path/URI."""
        pass

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if a file exists at the given storage path/URI."""
        pass

    def delete(self, file_path: str) -> bool:
        """Delete a file or directory at the given storage path/URI. Return True if deleted, False otherwise."""
        return False

    def get_file_size(self, file_path: str) -> int:
        """Return file size in bytes."""
        return len(self.read_bytes(file_path))

    def generate_presigned_upload_url(
        self,
        file_path: str,
        content_type: Optional[str] = None,
        expires_in: int = 900,
    ) -> Optional[str]:
        """Generate a presigned PUT URL for direct client upload, or None if unsupported."""
        return None

    def generate_presigned_download_url(
        self,
        file_path: str,
        filename: Optional[str] = None,
        expires_in: int = 900,
    ) -> Optional[str]:
        """Generate a presigned GET URL for direct client download, or None if unsupported."""
        return None


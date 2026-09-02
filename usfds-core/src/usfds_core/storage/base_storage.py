from abc import ABC, abstractmethod


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

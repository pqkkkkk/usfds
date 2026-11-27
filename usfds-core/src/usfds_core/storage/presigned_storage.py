"""IFileStorage implementation backed purely by pre-signed HTTP GET/PUT URLs (ISS-009)."""
from typing import Dict, Optional, Set
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from usfds_core.storage.base_storage import IFileStorage


class PresignedUrlStorage(IFileStorage):
	"""Read/write storage adapter using pre-signed URLs without holding object-storage credentials."""

	def __init__(
		self,
		read_urls: Optional[Dict[str, str]] = None,
		write_urls: Optional[Dict[str, str]] = None,
		timeout_seconds: float = 120.0,
	):
		self._read_urls: Dict[str, str] = {
			self._normalize(k): v for k, v in (read_urls or {}).items()
		}
		self._write_urls: Dict[str, str] = {
			self._normalize(k): v for k, v in (write_urls or {}).items()
		}
		self._timeout_seconds = timeout_seconds
		self._written_paths: Set[str] = set()

	@staticmethod
	def _normalize(file_path: str) -> str:
		return str(file_path).replace("\\", "/").lstrip("/")

	def exists(self, file_path: str) -> bool:
		norm = self._normalize(file_path)
		return norm in self._read_urls or norm in self._written_paths

	def read_bytes(self, file_path: str) -> bytes:
		norm = self._normalize(file_path)
		url = self._read_urls.get(norm)
		if not url:
			raise FileNotFoundError(f"No presigned GET URL mapped for path '{file_path}'.")

		req = Request(url=url, method="GET")
		try:
			with urlopen(req, timeout=self._timeout_seconds) as resp:
				return resp.read()
		except HTTPError as exc:
			if exc.code in (401, 403):
				raise PermissionError(
					f"Presigned GET URL expired or unauthorized for '{file_path}' (HTTP {exc.code})."
				) from exc
			if exc.code == 404:
				raise FileNotFoundError(
					f"Object not found at presigned GET URL for '{file_path}' (HTTP 404)."
				) from exc
			raise RuntimeError(
				f"Failed to download '{file_path}' via presigned GET URL (HTTP {exc.code})."
			) from exc
		except URLError as exc:
			raise RuntimeError(
				f"Network error downloading '{file_path}' via presigned GET URL: {exc.reason}"
			) from exc

	def save_bytes(self, file_path: str, data: bytes) -> str:
		norm = self._normalize(file_path)
		url = self._write_urls.get(norm)
		if not url:
			raise KeyError(f"No presigned PUT URL mapped for path '{file_path}'.")

		req = Request(
			url=url,
			data=data,
			method="PUT",
			headers={"Content-Type": "application/octet-stream"},
		)
		try:
			with urlopen(req, timeout=self._timeout_seconds) as resp:
				# Consume any response body so the underlying connection closes cleanly.
				resp.read()
		except HTTPError as exc:
			if exc.code in (401, 403):
				raise PermissionError(
					f"Presigned PUT URL expired or unauthorized for '{file_path}' (HTTP {exc.code})."
				) from exc
			raise RuntimeError(
				f"Failed to upload '{file_path}' via presigned PUT URL (HTTP {exc.code})."
			) from exc
		except URLError as exc:
			raise RuntimeError(
				f"Network error uploading '{file_path}' via presigned PUT URL: {exc.reason}"
			) from exc

		self._written_paths.add(norm)
		return file_path

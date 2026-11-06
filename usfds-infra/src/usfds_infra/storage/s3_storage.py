from pathlib import Path
from typing import Any, List, Optional, Union

from usfds_core.storage.base_storage import IFileStorage


class S3FileStorage(IFileStorage):
	"""S3-compatible object storage implementation of IFileStorage (RustFS, MinIO, AWS S3, R2).

	Storage paths are object keys inside a single bucket. Unlike LocalFileStorage, `save_*`
	returns the object key (not an absolute path), so the same value can be read back on any host.
	"""

	def __init__(
		self,
		bucket: str,
		endpoint_url: Optional[str] = None,
		access_key: Optional[str] = None,
		secret_key: Optional[str] = None,
		region: str = "us-east-1",
		client: Optional[Any] = None,
		create_bucket: bool = True,
	):
		self.bucket = bucket
		self._client = client or self._build_client(endpoint_url, access_key, secret_key, region)
		if create_bucket:
			self.ensure_bucket()

	@staticmethod
	def _build_client(endpoint_url, access_key, secret_key, region):
		import boto3
		from botocore.config import Config

		return boto3.client(
			"s3",
			endpoint_url=endpoint_url,
			aws_access_key_id=access_key,
			aws_secret_access_key=secret_key,
			region_name=region,
			# Path-style addressing is required by RustFS / MinIO on a plain host:port endpoint.
			config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
		)

	@staticmethod
	def _key(file_path: Union[str, Path]) -> str:
		return str(file_path).replace("\\", "/").lstrip("/")

	def ensure_bucket(self) -> None:
		"""Create the bucket if it does not exist yet (idempotent, safe across server/worker start-up races)."""
		from botocore.exceptions import ClientError

		try:
			self._client.head_bucket(Bucket=self.bucket)
			return
		except ClientError:
			pass
		try:
			self._client.create_bucket(Bucket=self.bucket)
		except ClientError as e:
			code = e.response.get("Error", {}).get("Code", "")
			if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
				raise

	def save_bytes(self, file_path: str, data: bytes) -> str:
		key = self._key(file_path)
		self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
		return key

	def read_bytes(self, file_path: str) -> bytes:
		from botocore.exceptions import ClientError

		key = self._key(file_path)
		try:
			return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
		except ClientError as e:
			if e.response.get("Error", {}).get("Code", "") in ("NoSuchKey", "404"):
				raise FileNotFoundError(f"File not found in object storage: s3://{self.bucket}/{key}") from e
			raise

	def exists(self, file_path: str) -> bool:
		from botocore.exceptions import ClientError

		try:
			self._client.head_object(Bucket=self.bucket, Key=self._key(file_path))
			return True
		except ClientError as e:
			if e.response.get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound"):
				return False
			raise

	def delete(self, file_path: str) -> bool:
		"""Delete an object, or every object under the key used as a prefix. Returns True if anything was deleted."""
		key = self._key(file_path)
		if self.exists(key):
			self._client.delete_object(Bucket=self.bucket, Key=key)
			return True
		keys = self.list_files(key)
		for k in keys:
			self._client.delete_object(Bucket=self.bucket, Key=k)
		return bool(keys)

	def save_file(self, src_path: Union[str, Path], dest_path: str) -> str:
		"""Upload a local file without loading it fully into memory."""
		src = Path(src_path).resolve()
		if not src.is_file():
			raise FileNotFoundError(f"Source file does not exist: {src}")
		key = self._key(dest_path)
		self._client.upload_file(str(src), self.bucket, key)
		return key

	def get_file_size(self, file_path: str) -> int:
		from botocore.exceptions import ClientError

		key = self._key(file_path)
		try:
			return int(self._client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
		except ClientError as e:
			if e.response.get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound"):
				raise FileNotFoundError(f"File not found in object storage: s3://{self.bucket}/{key}") from e
			raise

	def list_files(self, subdir: str = "") -> List[str]:
		"""List object keys under a "directory" (prefix with trailing '/'), sorted. Never matches sibling prefixes."""
		prefix = self._key(subdir)
		if prefix and not prefix.endswith("/"):
			prefix += "/"
		keys: List[str] = []
		paginator = self._client.get_paginator("list_objects_v2")
		for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
			keys.extend(obj["Key"] for obj in page.get("Contents", []))
		return sorted(keys)

	def ping(self) -> bool:
		"""Return True when the bucket is reachable (used by health checks)."""
		try:
			self._client.head_bucket(Bucket=self.bucket)
			return True
		except Exception:
			return False

from pathlib import Path
from typing import Any, List, Optional, Union

from usfds_core.storage.base_storage import IFileStorage


def _client_error_cls() -> type[Exception]:
	try:
		from botocore.exceptions import ClientError

		return ClientError
	except ImportError:
		return Exception



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
		public_endpoint_url: Optional[str] = None,
	):
		self.bucket = bucket
		self._client = client or self._build_client(endpoint_url, access_key, secret_key, region)
		self._presign_client = (
			self._build_client(public_endpoint_url, access_key, secret_key, region)
			if (public_endpoint_url and client is None)
			else self._client
		)
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
		client_err = _client_error_cls()

		bucket_ready = False
		try:
			self._client.head_bucket(Bucket=self.bucket)
			bucket_ready = True
		except client_err:
			pass
		if not bucket_ready:
			try:
				self._client.create_bucket(Bucket=self.bucket)
			except client_err as e:
				code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
				if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
					raise
		if hasattr(self._client, "put_bucket_cors"):
			try:
				self._client.put_bucket_cors(
					Bucket=self.bucket,
					CORSConfiguration={
						"CORSRules": [
							{
								"AllowedHeaders": ["*"],
								"AllowedMethods": ["GET", "PUT", "HEAD"],
								"AllowedOrigins": ["*"],
								"ExposeHeaders": ["ETag", "Content-Length", "Content-Disposition"],
								"MaxAgeSeconds": 3600,
							}
						]
					},
				)
			except Exception:
				pass

	def save_bytes(self, file_path: str, data: bytes) -> str:
		key = self._key(file_path)
		self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
		return key

	def read_bytes(self, file_path: str) -> bytes:
		client_err = _client_error_cls()

		key = self._key(file_path)
		try:
			return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
		except client_err as e:
			if getattr(e, "response", {}).get("Error", {}).get("Code", "") in ("NoSuchKey", "404"):
				raise FileNotFoundError(f"File not found in object storage: s3://{self.bucket}/{key}") from e
			raise

	def exists(self, file_path: str) -> bool:
		client_err = _client_error_cls()

		try:
			self._client.head_object(Bucket=self.bucket, Key=self._key(file_path))
			return True
		except client_err as e:
			if getattr(e, "response", {}).get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound"):
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
		"""Upload a local file or copy an existing S3 object key to `dest_path` without loading it into memory."""
		local_src = Path(src_path)
		key = self._key(dest_path)
		if local_src.is_file():
			self._client.upload_file(str(local_src.resolve()), self.bucket, key)
			return key
		src_key = self._key(src_path)
		if self.exists(src_key):
			if src_key != key:
				if hasattr(self._client, "copy_object"):
					self._client.copy_object(
						Bucket=self.bucket,
						CopySource={"Bucket": self.bucket, "Key": src_key},
						Key=key,
					)
				else:
					self.save_bytes(key, self.read_bytes(src_key))
			return key
		raise FileNotFoundError(f"Source file does not exist: {src_path}")

	def generate_presigned_upload_url(
		self,
		file_path: str,
		content_type: Optional[str] = None,
		expires_in: int = 900,
	) -> str:
		"""Generate an S3v4 presigned PUT URL for direct client upload."""
		key = self._key(file_path)
		params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
		if content_type:
			params["ContentType"] = content_type
		return str(
			self._presign_client.generate_presigned_url(
				"put_object",
				Params=params,
				ExpiresIn=expires_in,
			)
		)

	def generate_presigned_download_url(
		self,
		file_path: str,
		filename: Optional[str] = None,
		expires_in: int = 900,
	) -> str:
		"""Generate an S3v4 presigned GET URL for direct client download."""
		key = self._key(file_path)
		if not self.exists(key):
			raise FileNotFoundError(f"File not found in object storage: s3://{self.bucket}/{key}")
		dl_name = filename or Path(key).name
		params: dict[str, Any] = {
			"Bucket": self.bucket,
			"Key": key,
			"ResponseContentDisposition": f'attachment; filename="{dl_name}"',
		}
		return str(
			self._presign_client.generate_presigned_url(
				"get_object",
				Params=params,
				ExpiresIn=expires_in,
			)
		)

	def get_file_size(self, file_path: str) -> int:
		client_err = _client_error_cls()

		key = self._key(file_path)
		try:
			return int(self._client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
		except client_err as e:
			if getattr(e, "response", {}).get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound"):
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

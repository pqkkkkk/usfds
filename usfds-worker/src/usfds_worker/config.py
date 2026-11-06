import os
from dataclasses import dataclass


def _require(name: str) -> str:
	value = os.getenv(name)
	if not value:
		raise RuntimeError(f"Environment variable {name} is required by usfds-worker")
	return value


@dataclass(frozen=True)
class WorkerSettings:
	db_url: str
	s3_endpoint_url: str
	s3_bucket: str
	s3_access_key: str
	s3_secret_key: str
	s3_region: str = "us-east-1"
	bullmq_schema: str = "bullmq"
	concurrency: int = 1
	lock_duration_ms: int = 60_000

	@classmethod
	def from_env(cls) -> "WorkerSettings":
		return cls(
			db_url=_require("USFDS_DB_URL"),
			s3_endpoint_url=_require("USFDS_S3_ENDPOINT_URL"),
			s3_bucket=os.getenv("USFDS_S3_BUCKET", "usfds"),
			s3_access_key=_require("USFDS_S3_ACCESS_KEY"),
			s3_secret_key=_require("USFDS_S3_SECRET_KEY"),
			s3_region=os.getenv("USFDS_S3_REGION", "us-east-1"),
			bullmq_schema=os.getenv("USFDS_BULLMQ_SCHEMA", "bullmq"),
			concurrency=int(os.getenv("USFDS_WORKER_CONCURRENCY", "1")),
			lock_duration_ms=int(os.getenv("USFDS_WORKER_LOCK_MS", "60000")),
		)

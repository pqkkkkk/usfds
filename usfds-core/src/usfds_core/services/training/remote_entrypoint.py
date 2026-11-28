"""Sandbox entrypoint executed inside remote Modal containers (ISS-009)."""
import argparse
import os
import sys
from typing import Optional
from urllib.request import Request, urlopen

from usfds_core.domain.schemas.training_payload import RemoteTrainingJobSpec
from usfds_core.services.training.executor import TrainingRunExecutor
from usfds_core.storage.presigned_storage import PresignedUrlStorage

RESULT_SENTINEL = "__USFDS_RESULT_JSON__:"


def fetch_remote_job_spec(spec_url: str, timeout_seconds: float = 60.0) -> RemoteTrainingJobSpec:
	"""Fetch and validate RemoteTrainingJobSpec JSON from a presigned GET URL."""
	req = Request(url=spec_url, method="GET")
	with urlopen(req, timeout=timeout_seconds) as resp:
		raw_json = resp.read().decode("utf-8")
	return RemoteTrainingJobSpec.model_validate_json(raw_json)


def main(argv: Optional[list[str]] = None) -> int:
	"""Fetch job spec from USFDS_SPEC_GET_URL, run TrainingRunExecutor, and print sentinel JSON."""
	parser = argparse.ArgumentParser(description="USFDS remote training sandbox entrypoint")
	parser.add_argument("--spec-url", default=None, help="Presigned GET URL for remote_job_spec.json")
	args, _ = parser.parse_known_args(argv)

	spec_url = args.spec_url or os.getenv("USFDS_SPEC_GET_URL", "").strip()
	if not spec_url:
		print("Missing USFDS_SPEC_GET_URL environment variable or --spec-url argument.", file=sys.stderr)
		return 2

	spec = fetch_remote_job_spec(spec_url)
	storage = PresignedUrlStorage(
		read_urls=spec.read_urls,
		write_urls=spec.write_urls,
	)
	executor = TrainingRunExecutor(file_storage=storage)
	result = executor.run(spec.payload)
	print(f"{RESULT_SENTINEL}{result.model_dump_json()}", flush=True)
	return 0 if result.is_success else 1


if __name__ == "__main__":
	sys.exit(main())

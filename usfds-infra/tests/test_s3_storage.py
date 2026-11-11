import unittest

from usfds_infra.storage.s3_storage import S3FileStorage


class _FakeClientError(Exception):
	def __init__(self, response, operation_name):
		super().__init__(operation_name)
		self.response = response



class _FakeS3Client:
	"""Minimal in-memory stand-in for a boto3 S3 client (no network, no Docker)."""

	def __init__(self):
		self.objects = {}

	def head_bucket(self, Bucket):
		return {}

	def put_object(self, Bucket, Key, Body):
		self.objects[Key] = Body

	def get_object(self, Bucket, Key):
		if Key not in self.objects:
			raise _FakeClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
		body = self.objects[Key]
		return {"Body": type("B", (), {"read": lambda self_: body})()}

	def head_object(self, Bucket, Key):
		if Key not in self.objects:
			raise _FakeClientError({"Error": {"Code": "404"}}, "HeadObject")
		return {"ContentLength": len(self.objects[Key])}

	def delete_object(self, Bucket, Key):
		self.objects.pop(Key, None)

	def copy_object(self, Bucket, CopySource, Key):
		self.objects[Key] = self.objects[CopySource["Key"]]

	def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
		return f"http://localhost:9000/{Params['Bucket']}/{Params['Key']}?method={ClientMethod}&exp={ExpiresIn}"

	def get_paginator(self, name):
		objects = self.objects

		class _Paginator:
			def paginate(self_, Bucket, Prefix):
				return [{"Contents": [{"Key": k} for k in objects if k.startswith(Prefix)]}]

		return _Paginator()


class TestS3FileStorage(unittest.TestCase):
	def setUp(self):
		self.client = _FakeS3Client()
		self.storage = S3FileStorage(bucket="usfds", client=self.client)

	def test_round_trip_returns_key_and_missing_raises(self):
		key = self.storage.save_bytes("/models/m1/run1/model.joblib", b"abc")
		self.assertEqual(key, "models/m1/run1/model.joblib")
		self.assertTrue(self.storage.exists(key))
		self.assertEqual(self.storage.read_bytes(key), b"abc")
		self.assertEqual(self.storage.get_file_size(key), 3)
		with self.assertRaises(FileNotFoundError):
			self.storage.read_bytes("models/none.bin")

	def test_delete_prefix_does_not_touch_sibling_prefix(self):
		self.storage.save_bytes("datasets/a/raw.csv", b"1")
		self.storage.save_bytes("datasets/ab/raw.csv", b"2")
		self.assertTrue(self.storage.delete("datasets/a"))
		self.assertFalse(self.storage.exists("datasets/a/raw.csv"))
		self.assertTrue(self.storage.exists("datasets/ab/raw.csv"))

	def test_save_file_from_s3_key_and_presigned_urls(self):
		self.storage.save_bytes("uploads/dataset_raw/global/u1/raw.csv", b"a,b\n1,2\n")
		copied_key = self.storage.save_file(
			"uploads/dataset_raw/global/u1/raw.csv",
			"datasets/d1/raw/raw.csv",
		)
		self.assertEqual(copied_key, "datasets/d1/raw/raw.csv")
		self.assertEqual(self.storage.read_bytes(copied_key), b"a,b\n1,2\n")

		put_url = self.storage.generate_presigned_upload_url("uploads/test.csv", content_type="text/csv", expires_in=600)
		self.assertIn("http://localhost:9000/usfds/uploads/test.csv", put_url)
		self.assertIn("method=put_object", put_url)

		get_url = self.storage.generate_presigned_download_url(copied_key, filename="export.csv", expires_in=600)
		self.assertIn("http://localhost:9000/usfds/datasets/d1/raw/raw.csv", get_url)
		self.assertIn("method=get_object", get_url)


if __name__ == "__main__":
	unittest.main()

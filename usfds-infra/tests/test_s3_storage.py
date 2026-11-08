import unittest

from botocore.exceptions import ClientError

from usfds_infra.storage.s3_storage import S3FileStorage


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
			raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
		body = self.objects[Key]
		return {"Body": type("B", (), {"read": lambda self_: body})()}

	def head_object(self, Bucket, Key):
		if Key not in self.objects:
			raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
		return {"ContentLength": len(self.objects[Key])}

	def delete_object(self, Bucket, Key):
		self.objects.pop(Key, None)

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


if __name__ == "__main__":
	unittest.main()

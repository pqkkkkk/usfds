import os
import shutil
import tempfile
import unittest

from usfds_infra.storage.local_storage import LocalFileStorage


class TestLocalFileStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="usfds_storage_test_")
        self.storage = LocalFileStorage(base_dir=self.temp_dir)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_save_and_read_bytes(self):
        rel_path = "nested/dir/test_file.txt"
        data = b"Hello USFDS Local Storage!"

        saved_path = self.storage.save_bytes(rel_path, data)
        self.assertTrue(os.path.exists(saved_path))
        self.assertTrue(self.storage.exists(rel_path))

        read_data = self.storage.read_bytes(rel_path)
        self.assertEqual(read_data, data)

    def test_read_non_existent_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.read_bytes("non_existent_file.parquet")

    def test_exists(self):
        self.assertFalse(self.storage.exists("missing.csv"))
        self.storage.save_bytes("data.bin", b"\x00\x01\x02")
        self.assertTrue(self.storage.exists("data.bin"))


if __name__ == "__main__":
    unittest.main()

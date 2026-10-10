import os
from pathlib import Path
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

    def test_delete(self):
        rel_path = "to_delete.txt"
        self.storage.save_bytes(rel_path, b"delete me")
        self.assertTrue(self.storage.exists(rel_path))
        deleted = self.storage.delete(rel_path)
        self.assertTrue(deleted)
        self.assertFalse(self.storage.exists(rel_path))

        # Deleting non-existent returns False
        self.assertFalse(self.storage.delete("non_existent.txt"))

    def test_save_file_and_get_size(self):
        src_file = Path(self.temp_dir) / "source.bin"
        src_data = b"x" * 1024
        src_file.write_bytes(src_data)

        dest_rel = "dest/copied.bin"
        self.storage.save_file(src_file, dest_rel)

        self.assertTrue(self.storage.exists(dest_rel))
        self.assertEqual(self.storage.get_file_size(dest_rel), 1024)

    def test_list_files(self):
        self.storage.save_bytes("folder1/a.txt", b"a")
        self.storage.save_bytes("folder1/b.txt", b"b")
        self.storage.save_bytes("folder2/c.txt", b"c")

        files_all = self.storage.list_files()
        self.assertEqual(files_all, ["folder1/a.txt", "folder1/b.txt", "folder2/c.txt"])

        files_f1 = self.storage.list_files("folder1")
        self.assertEqual(files_f1, ["folder1/a.txt", "folder1/b.txt"])


if __name__ == "__main__":
    unittest.main()

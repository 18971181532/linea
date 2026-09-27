"""Tests for file hashing."""
import os
import unittest

from linea.hasher import hash_file, hash_files, hash_string, hash_directory
from tests.helpers import TempStore


class TestHasher(unittest.TestCase):
    def test_hash_file(self):
        with TempStore() as ts:
            path = ts.write_file("test.txt", "hello world")
            h = hash_file(path)
            self.assertEqual(len(h), 64)
            self.assertEqual(h, hash_file(path))  # deterministic

    def test_hash_different_content(self):
        with TempStore() as ts:
            p1 = ts.write_file("a.txt", "aaa")
            p2 = ts.write_file("b.txt", "bbb")
            self.assertNotEqual(hash_file(p1), hash_file(p2))

    def test_hash_files(self):
        with TempStore() as ts:
            ts.write_file("a.txt", "aaa")
            ts.write_file("b.txt", "bbb")
            results = hash_files(["a.txt", "b.txt"], base_dir=ts.dir)
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0]["exists"])
            self.assertEqual(results[0]["size"], 3)

    def test_hash_missing_file(self):
        with TempStore() as ts:
            results = hash_files(["nonexistent.txt"], base_dir=ts.dir)
            self.assertFalse(results[0]["exists"])
            self.assertIsNone(results[0]["sha256"])

    def test_hash_string(self):
        h = hash_string("test")
        self.assertEqual(len(h), 64)
        self.assertEqual(h, hash_string("test"))

    def test_hash_directory(self):
        with TempStore() as ts:
            ts.write_file("dir/a.txt", "aaa")
            ts.write_file("dir/b.txt", "bbb")
            results = hash_directory("dir", base_dir=ts.dir)
            self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()

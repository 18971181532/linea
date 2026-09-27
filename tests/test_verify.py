"""Tests for reproducibility verification."""
import os
import unittest

from linea.store import Store
from linea.verify import verify_run, verify_file
from tests.helpers import TempStore


class TestVerify(unittest.TestCase):
    def test_verify_reproducible(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            ts.write_file("input.txt", "hello")
            cmd = "type input.txt > output.txt" if os.name == "nt" else "cat input.txt > output.txt"
            store.save_run({
                "id": "run_v1", "command": cmd, "cwd": ts.dir,
                "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "input.txt", "sha256": "x"}],
                "outputs": [{"path": "output.txt", "sha256": None}],
            })
            # First, hash the output after running
            from linea.hasher import hash_file
            os.system(f'cd /d "{ts.dir}" && {cmd}' if os.name == "nt" else f'cd "{ts.dir}" && {cmd}')
            out_hash = hash_file(os.path.join(ts.dir, "output.txt"))
            store.save_run({
                "id": "run_v1", "command": cmd, "cwd": ts.dir,
                "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "input.txt", "sha256": "x"}],
                "outputs": [{"path": "output.txt", "sha256": out_hash}],
            })
            result = verify_run("run_v1", store)
            self.assertTrue(result.reproducible)

    def test_verify_missing_run(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            result = verify_run("nonexistent", store)
            self.assertFalse(result.reproducible)
            self.assertIn("error", result.details)

    def test_verify_file_no_run(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            result = verify_file("unknown.txt", store)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

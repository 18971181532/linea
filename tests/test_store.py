"""Tests for the provenance store."""
import unittest

from linea.store import Store
from tests.helpers import TempStore


class TestStore(unittest.TestCase):
    def test_init(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            self.assertTrue(store.exists())

    def test_save_and_get_run(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            run = {"id": "test_run_1", "command": "echo hi", "exit_code": 0,
                   "inputs": [], "outputs": []}
            store.save_run(run)
            loaded = store.get_run("test_run_1")
            self.assertEqual(loaded["command"], "echo hi")

    def test_list_runs(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            for i in range(5):
                store.save_run({"id": f"run_{i}", "command": f"cmd {i}",
                                "exit_code": 0, "inputs": [], "outputs": []})
            runs = store.list_runs()
            self.assertEqual(len(runs), 5)

    def test_list_runs_limit(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            for i in range(10):
                store.save_run({"id": f"run_{i}", "command": f"cmd {i}",
                                "exit_code": 0, "inputs": [], "outputs": []})
            runs = store.list_runs(limit=3)
            self.assertEqual(len(runs), 3)

    def test_find_by_output(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "run_1", "command": "process", "exit_code": 0,
                "inputs": [{"path": "in.csv"}],
                "outputs": [{"path": "out.json", "sha256": "abc"}],
            })
            found = store.find_runs_by_output("out.json")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["id"], "run_1")

    def test_find_by_input(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "run_1", "command": "process", "exit_code": 0,
                "inputs": [{"path": "in.csv"}],
                "outputs": [],
            })
            found = store.find_runs_by_input("in.csv")
            self.assertEqual(len(found), 1)

    def test_stats(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({"id": "r1", "command": "c", "exit_code": 0,
                            "inputs": [{"path": "a"}], "outputs": [{"path": "b"}]})
            store.save_run({"id": "r2", "command": "c", "exit_code": 1,
                            "inputs": [{"path": "b"}], "outputs": [{"path": "c"}]})
            s = store.stats()
            self.assertEqual(s["total_runs"], 2)
            self.assertEqual(s["successful"], 1)
            self.assertEqual(s["failed"], 1)
            self.assertEqual(s["unique_files"], 3)


if __name__ == "__main__":
    unittest.main()

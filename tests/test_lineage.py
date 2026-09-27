"""Tests for lineage analysis."""
import unittest

from linea.lineage import Lineage
from linea.store import Store
from tests.helpers import TempStore


def _make_chain(store):
    """Create a 3-step chain: raw -> clean -> result."""
    store.save_run({
        "id": "r1", "command": "clean raw.csv", "exit_code": 0,
        "inputs": [{"path": "raw.csv", "sha256": "aaa"}],
        "outputs": [{"path": "clean.csv", "sha256": "bbb"}],
    })
    store.save_run({
        "id": "r2", "command": "analyze clean.csv", "exit_code": 0,
        "inputs": [{"path": "clean.csv", "sha256": "bbb"}],
        "outputs": [{"path": "result.json", "sha256": "ccc"}],
    })
    store.save_run({
        "id": "r3", "command": "report result.json", "exit_code": 0,
        "inputs": [{"path": "result.json", "sha256": "ccc"}],
        "outputs": [{"path": "report.txt", "sha256": "ddd"}],
    })


class TestLineage(unittest.TestCase):
    def test_trace(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            _make_chain(store)
            lin = Lineage(store)
            tree = lin.trace("report.txt")
            self.assertEqual(tree["file"], "report.txt")
            self.assertIsNotNone(tree["produced_by"])
            self.assertEqual(len(tree["inputs"]), 1)
            self.assertEqual(tree["inputs"][0]["file"], "result.json")
            # deep trace
            self.assertEqual(tree["inputs"][0]["inputs"][0]["file"], "clean.csv")

    def test_trace_external(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            lin = Lineage(store)
            tree = lin.trace("unknown.txt")
            self.assertIsNone(tree["produced_by"])
            self.assertEqual(tree.get("source"), "external")

    def test_impact(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            _make_chain(store)
            lin = Lineage(store)
            downstream = lin.all_downstream_files("raw.csv")
            self.assertIn("clean.csv", downstream)
            self.assertIn("result.json", downstream)
            self.assertIn("report.txt", downstream)

    def test_impact_middle(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            _make_chain(store)
            lin = Lineage(store)
            downstream = lin.all_downstream_files("clean.csv")
            self.assertIn("result.json", downstream)
            self.assertIn("report.txt", downstream)
            self.assertNotIn("clean.csv", downstream)

    def test_orphans(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            ts.write_file("tracked.txt", "data")
            ts.write_file("orphan.txt", "orphan")
            store.save_run({
                "id": "r1", "command": "c", "exit_code": 0,
                "inputs": [{"path": "tracked.txt"}],
                "outputs": [],
            })
            lin = Lineage(store)
            orphans = lin.orphans()
            paths = [o["path"] for o in orphans]
            self.assertIn("orphan.txt", paths)
            self.assertNotIn("tracked.txt", paths)

    def test_compare_runs(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "r1", "command": "cmd", "exit_code": 0, "duration_ms": 100,
                "inputs": [{"path": "a.csv", "sha256": "aaa"}],
                "outputs": [{"path": "b.json", "sha256": "bbb"}],
            })
            store.save_run({
                "id": "r2", "command": "cmd", "exit_code": 0, "duration_ms": 110,
                "inputs": [{"path": "a.csv", "sha256": "aaa"}],
                "outputs": [{"path": "b.json", "sha256": "ccc"}],
            })
            lin = Lineage(store)
            result = lin.compare_runs("r1", "r2")
            self.assertTrue(result["same_command"])
            self.assertEqual(len(result["files_changed"]), 1)
            self.assertEqual(result["files_changed"][0]["path"], "b.json")


if __name__ == "__main__":
    unittest.main()

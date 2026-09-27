"""Tests for graph construction."""
import unittest

from linea.graph import build_graph, layout_graph
from linea.store import Store
from tests.helpers import TempStore


class TestGraph(unittest.TestCase):
    def test_build_graph(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "r1", "command": "process", "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "in.csv", "sha256": "aaa", "size": 100}],
                "outputs": [{"path": "out.json", "sha256": "bbb", "size": 50}],
            })
            graph = build_graph(store)
            self.assertEqual(graph["stats"]["file_count"], 2)
            self.assertEqual(graph["stats"]["run_count"], 1)
            self.assertEqual(graph["stats"]["edge_count"], 2)

    def test_graph_node_types(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "r1", "command": "process", "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "in.csv", "sha256": "a", "size": 1}],
                "outputs": [{"path": "out.json", "sha256": "b", "size": 1}],
            })
            graph = build_graph(store)
            types = {n["type"] for n in graph["nodes"]}
            self.assertIn("file", types)
            self.assertIn("run", types)

    def test_layout_graph(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "r1", "command": "process", "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "in.csv", "sha256": "a", "size": 1}],
                "outputs": [{"path": "out.json", "sha256": "b", "size": 1}],
            })
            graph = build_graph(store)
            layout = layout_graph(graph, canvas_w=800, canvas_h=500)
            self.assertIn("positions", layout)
            self.assertEqual(len(layout["positions"]), 3)

    def test_focus_file(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            store.save_run({
                "id": "r1", "command": "p1", "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "a.csv", "sha256": "a", "size": 1}],
                "outputs": [{"path": "b.csv", "sha256": "b", "size": 1}],
            })
            store.save_run({
                "id": "r2", "command": "p2", "exit_code": 0, "duration_ms": 10,
                "inputs": [{"path": "unrelated.csv", "sha256": "x", "size": 1}],
                "outputs": [{"path": "other.json", "sha256": "y", "size": 1}],
            })
            graph = build_graph(store, focus_file="a.csv")
            run_ids = {n["id"] for n in graph["nodes"] if n["type"] == "run"}
            self.assertIn("r1", run_ids)
            self.assertNotIn("r2", run_ids)


if __name__ == "__main__":
    unittest.main()

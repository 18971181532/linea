"""Tests for the command runner."""
import os
import unittest

from linea.runner import run_command, capture_environment
from linea.store import Store
from tests.helpers import TempStore


class TestRunner(unittest.TestCase):
    def test_run_simple_command(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            ts.write_file("input.txt", "hello")
            run = run_command(
                command="type input.txt > output.txt" if os.name == "nt" else "cat input.txt > output.txt",
                inputs=["input.txt"],
                outputs=["output.txt"],
                store=store,
                cwd=ts.dir,
            )
            self.assertEqual(run["exit_code"], 0)
            self.assertTrue(os.path.exists(os.path.join(ts.dir, "output.txt")))
            self.assertEqual(len(run["inputs"]), 1)
            self.assertEqual(len(run["outputs"]), 1)
            self.assertIsNotNone(run["outputs"][0]["sha256"])

    def test_run_failing_command(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            run = run_command(
                command="exit 1" if os.name != "nt" else "cmd /c exit 1",
                inputs=[], outputs=[],
                store=store, cwd=ts.dir,
            )
            self.assertNotEqual(run["exit_code"], 0)

    def test_capture_environment(self):
        env = capture_environment(".")
        self.assertIn("os", env)
        self.assertIn("python", env)
        self.assertIn("cwd", env)

    def test_run_with_tags(self):
        with TempStore() as ts:
            store = Store(base_dir=ts.dir)
            run = run_command(
                command="echo test",
                inputs=[], outputs=[],
                store=store, cwd=ts.dir,
                tags=["experiment", "v1"],
            )
            self.assertIn("experiment", run["tags"])
            self.assertIn("v1", run["tags"])


if __name__ == "__main__":
    unittest.main()

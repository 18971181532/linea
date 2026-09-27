"""CLI end-to-end tests."""
import io
import os
import unittest
from contextlib import redirect_stdout, redirect_stderr

from linea.cli import main
from tests.helpers import TempStore


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


class TestCLI(unittest.TestCase):
    def test_init(self):
        import tempfile
        d = tempfile.mkdtemp()
        try:
            code, out, _ = run_cli("-C", d, "init")
            self.assertEqual(code, 0)
            self.assertIn("Initialized", out)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_stats_empty(self):
        with TempStore() as ts:
            code, out, _ = run_cli("-C", ts.dir, "stats")
            self.assertEqual(code, 0)
            self.assertIn("Runs:", out)

    def test_list_empty(self):
        with TempStore() as ts:
            code, out, _ = run_cli("-C", ts.dir, "list")
            self.assertEqual(code, 0)
            self.assertIn("No runs", out)

    def test_run_echo(self):
        with TempStore() as ts:
            code, out, _ = run_cli("-C", ts.dir, "run", "echo", "hello")
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_no_command(self):
        code, _, _ = run_cli()
        self.assertEqual(code, 1)

    def test_orphans(self):
        with TempStore() as ts:
            ts.write_file("loose.txt", "data")
            code, out, _ = run_cli("-C", ts.dir, "orphans")
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

"""Test helpers."""
import os
import tempfile


class TempStore:
    """Context manager: creates a temp dir with an initialized linea store."""
    def __init__(self):
        self.dir = None

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        from linea.store import Store
        store = Store(base_dir=self.dir)
        store.init()
        return self

    def __exit__(self, *args):
        import shutil
        if self.dir and os.path.exists(self.dir):
            shutil.rmtree(self.dir, ignore_errors=True)

    def write_file(self, relpath, content):
        full = os.path.join(self.dir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(full, mode) as f:
            f.write(content)
        return full

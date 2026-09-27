"""Lineage analysis — trace file ancestry, impact analysis, orphan detection."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, Tuple

from .store import Store


class Lineage:
    def __init__(self, store: Store):
        self.store = store

    def trace(self, path: str, max_depth: int = 20) -> Dict:
        """Trace the full ancestry of a file.

        Returns a tree structure:
        {
          "file": "result.json",
          "produced_by": {...run...},
          "inputs": [
            {"file": "data.csv", "produced_by": ..., "inputs": [...]},
            ...
          ]
        }
        """
        visited: Set[str] = set()
        return self._trace_recursive(path, visited, depth=0, max_depth=max_depth)

    def _trace_recursive(self, path: str, visited: Set[str],
                         depth: int, max_depth: int) -> Dict:
        node = {"file": path, "depth": depth}
        if depth >= max_depth or path in visited:
            node["truncated"] = depth >= max_depth
            return node
        visited.add(path)

        runs = self.store.find_runs_by_output(path)
        if runs:
            # Use the most recent run that produced this file
            run = runs[0]
            node["produced_by"] = {
                "id": run["id"],
                "command": run["command"],
                "exit_code": run.get("exit_code"),
                "duration_ms": run.get("duration_ms"),
                "started_at": run.get("started_at"),
            }
            node["inputs"] = []
            for inp in run.get("inputs", []):
                inp_path = inp.get("path", "")
                child = self._trace_recursive(inp_path, visited, depth + 1, max_depth)
                child["hash"] = inp.get("sha256")
                child["size"] = inp.get("size")
                node["inputs"].append(child)
        else:
            node["produced_by"] = None
            node["source"] = "external"  # not produced by any tracked run
        return node

    def impact(self, path: str, max_depth: int = 20) -> Dict:
        """Find all downstream files affected if this file changes.

        Returns a tree of downstream dependencies.
        """
        visited: Set[str] = set()
        return self._impact_recursive(path, visited, depth=0, max_depth=max_depth)

    def _impact_recursive(self, path: str, visited: Set[str],
                          depth: int, max_depth: int) -> Dict:
        node = {"file": path, "depth": depth}
        if depth >= max_depth or path in visited:
            node["truncated"] = depth >= max_depth
            return node
        visited.add(path)

        runs = self.store.find_runs_by_input(path)
        node["consumed_by"] = []
        for run in runs:
            consumer = {
                "id": run["id"],
                "command": run["command"],
                "outputs": [],
            }
            for out in run.get("outputs", []):
                out_path = out.get("path", "")
                child = self._impact_recursive(out_path, visited, depth + 1, max_depth)
                child["hash"] = out.get("sha256")
                consumer["outputs"].append(child)
            node["consumed_by"].append(consumer)
        return node

    def all_downstream_files(self, path: str) -> List[str]:
        """Flat list of all files downstream of a given file."""
        result: Set[str] = set()
        self._collect_downstream(path, set(), result)
        return sorted(result)

    def _collect_downstream(self, path: str, visited: Set[str], result: Set[str]) -> None:
        if path in visited:
            return
        visited.add(path)
        for run in self.store.find_runs_by_input(path):
            for out in run.get("outputs", []):
                out_path = out.get("path", "")
                if out_path:
                    result.add(out_path)
                    self._collect_downstream(out_path, visited, result)

    def orphans(self, scan_dir: Optional[str] = None,
                exclude: Optional[List[str]] = None) -> List[Dict]:
        """Find files in the project not tracked by any provenance run.

        Returns list of {path, size, mtime} for untracked files.
        """
        if scan_dir is None:
            scan_dir = self.store.base_dir
        if exclude is None:
            exclude = [".git", ".linea", "__pycache__", "node_modules",
                       ".venv", "venv", ".pytest_cache", "dist", "build",
                       ".idea", ".vscode"]

        tracked = set()
        for run in self.store.list_runs():
            for f in run.get("inputs", []) + run.get("outputs", []):
                p = f.get("path", "")
                if p:
                    tracked.add(os.path.normpath(p))
                    tracked.add(os.path.basename(p))

        orphans = []
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in exclude]
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, scan_dir).replace("\\", "/")
                norm = os.path.normpath(rel)
                if norm in tracked or fname in tracked:
                    continue
                try:
                    stat = os.stat(full)
                    orphans.append({
                        "path": rel,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    })
                except OSError:
                    pass
        return sorted(orphans, key=lambda x: -x["size"])

    def compare_runs(self, run_id_a: str, run_id_b: str) -> Dict:
        """Compare two runs: same command? inputs changed? outputs changed?"""
        a = self.store.get_run(run_id_a)
        b = self.store.get_run(run_id_b)
        if not a or not b:
            return {"error": "run not found"}

        def file_map(run):
            return {f["path"]: f.get("sha256") for f in run.get("inputs", []) + run.get("outputs", [])}

        fa, fb = file_map(a), file_map(b)
        all_files = set(fa) | set(fb)

        changed, added, removed = [], [], []
        for f in sorted(all_files):
            if f in fa and f in fb:
                if fa[f] != fb[f]:
                    changed.append({"path": f, "hash_a": fa[f], "hash_b": fb[f]})
            elif f in fa:
                removed.append(f)
            else:
                added.append(f)

        return {
            "run_a": run_id_a,
            "run_b": run_id_b,
            "same_command": a["command"] == b["command"],
            "command_a": a["command"],
            "command_b": b["command"],
            "exit_a": a.get("exit_code"),
            "exit_b": b.get("exit_code"),
            "duration_a": a.get("duration_ms"),
            "duration_b": b.get("duration_ms"),
            "files_changed": changed,
            "files_added": added,
            "files_removed": removed,
        }

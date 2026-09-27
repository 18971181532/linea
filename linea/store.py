"""Provenance store — persists run records as JSON files."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

STORE_DIR = ".linea"
RUNS_DIR = "runs"


class Store:
    def __init__(self, base_dir: str = "."):
        self.base_dir = os.path.abspath(base_dir)
        self.store_path = os.path.join(self.base_dir, STORE_DIR)
        self.runs_path = os.path.join(self.store_path, RUNS_DIR)

    def init(self) -> None:
        """Initialize the provenance store."""
        os.makedirs(self.runs_path, exist_ok=True)
        meta = {"version": 1, "created_at": time.time(), "base_dir": self.base_dir}
        with open(os.path.join(self.store_path, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

    def exists(self) -> bool:
        return os.path.isdir(self.runs_path)

    def _ensure(self) -> None:
        if not self.exists():
            raise FileNotFoundError(
                f"No linea store in {self.base_dir}. Run 'linea init' first."
            )

    def save_run(self, run: Dict) -> str:
        """Save a run record. Returns the run ID."""
        self._ensure()
        run_id = run.get("id") or f"run_{int(time.time()*1000)}"
        run["id"] = run_id
        path = os.path.join(self.runs_path, f"{run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(run, f, indent=2, ensure_ascii=False, default=str)
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict]:
        self._ensure()
        path = os.path.join(self.runs_path, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_runs(self, limit: int = 0, tag: Optional[str] = None) -> List[Dict]:
        self._ensure()
        runs = []
        for fname in sorted(os.listdir(self.runs_path), reverse=True):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(self.runs_path, fname), "r", encoding="utf-8") as f:
                run = json.load(f)
            if tag and tag not in run.get("tags", []):
                continue
            runs.append(run)
            if limit and len(runs) >= limit:
                break
        return runs

    def find_runs_by_output(self, path: str) -> List[Dict]:
        """Find all runs that produced a given file as output."""
        results = []
        for run in self.list_runs():
            for out in run.get("outputs", []):
                if out.get("path") == path or os.path.basename(out.get("path", "")) == os.path.basename(path):
                    results.append(run)
                    break
        return results

    def find_runs_by_input(self, path: str) -> List[Dict]:
        """Find all runs that consumed a given file as input."""
        results = []
        for run in self.list_runs():
            for inp in run.get("inputs", []):
                if inp.get("path") == path or os.path.basename(inp.get("path", "")) == os.path.basename(path):
                    results.append(run)
                    break
        return results

    def all_files(self) -> Dict[str, List[str]]:
        """Return mapping of file path -> list of run IDs where it appears (as input or output)."""
        mapping: Dict[str, List[str]] = {}
        for run in self.list_runs():
            rid = run["id"]
            for f in run.get("inputs", []) + run.get("outputs", []):
                p = f.get("path", "")
                if p not in mapping:
                    mapping[p] = []
                if rid not in mapping[p]:
                    mapping[p].append(rid)
        return mapping

    def delete_run(self, run_id: str) -> bool:
        path = os.path.join(self.runs_path, f"{run_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def stats(self) -> Dict:
        runs = self.list_runs()
        total_inputs = sum(len(r.get("inputs", [])) for r in runs)
        total_outputs = sum(len(r.get("outputs", [])) for r in runs)
        files = self.all_files()
        return {
            "total_runs": len(runs),
            "total_inputs": total_inputs,
            "total_outputs": total_outputs,
            "unique_files": len(files),
            "successful": sum(1 for r in runs if r.get("exit_code") == 0),
            "failed": sum(1 for r in runs if r.get("exit_code", 0) != 0),
        }

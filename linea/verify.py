"""Reproducibility verification — re-run commands and compare output hashes."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Dict, List, Optional

from .hasher import hash_files
from .store import Store


class VerificationResult:
    def __init__(self, run_id: str, reproducible: bool, details: Dict):
        self.run_id = run_id
        self.reproducible = reproducible
        self.details = details

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "reproducible": self.reproducible,
            **self.details,
        }


def verify_run(run_id: str, store: Store, timeout: int = 300) -> VerificationResult:
    """Re-execute a recorded run and compare output hashes.

    Args:
        run_id: The run to verify.
        store: The provenance store.
        timeout: Max seconds for the re-run.

    Returns:
        VerificationResult with per-file match status.
    """
    original = store.get_run(run_id)
    if not original:
        return VerificationResult(run_id, False, {"error": f"run {run_id} not found"})

    command = original["command"]
    cwd = original.get("cwd", store.base_dir)
    outputs = [o["path"] for o in original.get("outputs", [])]

    # Backup original output hashes
    original_hashes = {o["path"]: o.get("sha256") for o in original.get("outputs", [])}

    # Re-run
    started = time.time()
    try:
        proc = subprocess.run(
            command, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout,
        )
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        return VerificationResult(run_id, False, {
            "error": f"re-run timed out after {timeout}s",
            "command": command,
        })
    except Exception as e:
        return VerificationResult(run_id, False, {
            "error": str(e),
            "command": command,
        })
    duration_ms = round((time.time() - started) * 1000, 2)

    # Hash new outputs
    new_meta = hash_files(outputs, base_dir=cwd)
    new_hashes = {m["path"]: m.get("sha256") for m in new_meta}

    # Compare
    file_results = []
    all_match = True
    for path in sorted(set(original_hashes) | set(new_hashes)):
        orig_h = original_hashes.get(path)
        new_h = new_hashes.get(path)
        match = orig_h is not None and new_h is not None and orig_h == new_h
        if not match:
            all_match = False
        file_results.append({
            "path": path,
            "original_hash": orig_h,
            "new_hash": new_h,
            "match": match,
        })

    return VerificationResult(run_id, all_match and exit_code == original.get("exit_code"), {
        "command": command,
        "original_exit_code": original.get("exit_code"),
        "new_exit_code": exit_code,
        "original_duration_ms": original.get("duration_ms"),
        "new_duration_ms": duration_ms,
        "files": file_results,
        "exit_code_match": exit_code == original.get("exit_code"),
    })


def verify_file(path: str, store: Store) -> Optional[VerificationResult]:
    """Verify reproducibility of the run that produced a file."""
    runs = store.find_runs_by_output(path)
    if not runs:
        return None
    return verify_run(runs[0]["id"], store)

"""Command runner — wraps execution, captures inputs/outputs/environment."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from typing import Dict, List, Optional

from .hasher import hash_files, hash_string
from .store import Store


def capture_environment(cwd: str) -> Dict:
    """Capture a snapshot of the execution environment."""
    env = {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "cwd": os.path.abspath(cwd),
    }
    # git commit if in a repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        if result.returncode == 0:
            env["git_commit"] = result.stdout.strip()
        result2 = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        if result2.returncode == 0:
            env["git_dirty"] = bool(result2.stdout.strip())
    except Exception:
        pass
    # selected env vars
    for var in ("PATH", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV", "HOME", "USER"):
        val = os.environ.get(var)
        if val:
            env.setdefault("env", {})[var] = val
    return env


def run_command(
    command: str,
    inputs: List[str],
    outputs: List[str],
    store: Store,
    cwd: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: str = "",
    shell: bool = True,
) -> Dict:
    """Run a command and record its provenance.

    Args:
        command: The shell command to execute.
        inputs: List of input file paths (relative to cwd).
        outputs: List of expected output file paths.
        store: The provenance store to write to.
        cwd: Working directory (defaults to store.base_dir).
        tags: Optional tags for the run.
        notes: Optional free-text notes.
        shell: Whether to use shell execution.

    Returns:
        The saved run record dict.
    """
    if cwd is None:
        cwd = store.base_dir
    cwd = os.path.abspath(cwd)

    run_id = f"run_{int(time.time()*1000)}_{hash_string(command+str(time.time()))[:8]}"

    # Hash inputs BEFORE execution
    input_meta = hash_files(inputs, base_dir=cwd)

    # Record start
    started_at = time.time()
    env_snapshot = capture_environment(cwd)

    # Execute
    try:
        proc = subprocess.run(
            command, shell=shell, cwd=cwd,
            capture_output=True, text=True,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except Exception as e:
        exit_code = -1
        stdout = ""
        stderr = str(e)

    finished_at = time.time()

    # Hash outputs AFTER execution
    output_meta = hash_files(outputs, base_dir=cwd)

    run = {
        "id": run_id,
        "command": command,
        "cwd": cwd,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round((finished_at - started_at) * 1000, 2),
        "exit_code": exit_code,
        "stdout": stdout[-5000:] if len(stdout) > 5000 else stdout,
        "stderr": stderr[-5000:] if len(stderr) > 5000 else stderr,
        "inputs": input_meta,
        "outputs": output_meta,
        "environment": env_snapshot,
        "tags": tags or [],
        "notes": notes,
    }

    store.save_run(run)
    return run

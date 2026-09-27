"""File hashing utilities — SHA-256 with streaming for large files."""

from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional


def hash_file(path: str, algorithm: str = "sha256", chunk_size: int = 65536) -> str:
    """Compute hash of a file, streaming in chunks to handle large files."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_files(paths: List[str], base_dir: str = ".") -> List[Dict[str, object]]:
    """Hash multiple files, returning metadata dicts."""
    results = []
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(base_dir, p)
        if not os.path.exists(full):
            results.append({"path": p, "sha256": None, "size": 0, "exists": False})
            continue
        stat = os.stat(full)
        results.append({
            "path": p,
            "sha256": hash_file(full),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "exists": True,
        })
    return results


def hash_directory(path: str, base_dir: str = ".",
                   exclude_dirs: Optional[List[str]] = None) -> List[Dict[str, object]]:
    """Recursively hash all files in a directory."""
    if exclude_dirs is None:
        exclude_dirs = [".git", ".linea", "__pycache__", "node_modules", ".venv", "venv"]
    full = path if os.path.isabs(path) else os.path.join(base_dir, path)
    results = []
    for root, dirs, files in os.walk(full):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, base_dir)
            stat = os.stat(fpath)
            results.append({
                "path": rel.replace("\\", "/"),
                "sha256": hash_file(fpath),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "exists": True,
            })
    return results


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Hash a string (for commands, env snapshots, etc.)."""
    return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()

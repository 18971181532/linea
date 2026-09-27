"""Provenance graph construction — bipartite DAG of files and runs."""

from __future__ import annotations

from typing import Dict, List, Set

from .store import Store


def build_graph(store: Store, focus_file: str = None, max_runs: int = 50) -> Dict:
    """Build a bipartite graph: file nodes + run nodes.

    Nodes:
      - files: {id, type:"file", label, hash, size}
      - runs:  {id, type:"run", label, command, exit_code, duration_ms, timestamp}

    Edges:
      - input file -> run
      - run -> output file
    """
    runs = store.list_runs(limit=max_runs)

    # If focusing on a file, only include its connected component
    if focus_file:
        connected = _connected_component(focus_file, runs)
        runs = [r for r in runs if r["id"] in connected]

    file_nodes: Dict[str, Dict] = {}
    run_nodes: List[Dict] = []
    edges: List[Dict] = []

    for run in runs:
        rid = run["id"]
        run_nodes.append({
            "id": rid,
            "type": "run",
            "label": rid[:16],
            "command": run.get("command", "")[:80],
            "exit_code": run.get("exit_code"),
            "duration_ms": run.get("duration_ms"),
            "timestamp": run.get("started_at"),
            "tags": run.get("tags", []),
        })

        for inp in run.get("inputs", []):
            fid = f"file:{inp['path']}"
            if fid not in file_nodes:
                file_nodes[fid] = {
                    "id": fid,
                    "type": "file",
                    "label": inp["path"],
                    "hash": inp.get("sha256", "")[:12],
                    "size": inp.get("size", 0),
                }
            edges.append({"source": fid, "target": rid, "type": "input"})

        for out in run.get("outputs", []):
            fid = f"file:{out['path']}"
            if fid not in file_nodes:
                file_nodes[fid] = {
                    "id": fid,
                    "type": "file",
                    "label": out["path"],
                    "hash": out.get("sha256", "")[:12],
                    "size": out.get("size", 0),
                }
            edges.append({"source": rid, "target": fid, "type": "output"})

    nodes = list(file_nodes.values()) + run_nodes
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "file_count": len(file_nodes),
            "run_count": len(run_nodes),
            "edge_count": len(edges),
        },
    }


def _connected_component(file_path: str, runs: List[Dict]) -> Set[str]:
    """Find all run IDs connected (directly or transitively) to a file."""
    connected: Set[str] = set()
    frontier_files = {file_path}

    while frontier_files:
        next_files: Set[str] = set()
        for run in runs:
            rid = run["id"]
            if rid in connected:
                continue
            inputs = {i["path"] for i in run.get("inputs", [])}
            outputs = {o["path"] for o in run.get("outputs", [])}
            if inputs & frontier_files or outputs & frontier_files:
                connected.add(rid)
                next_files |= inputs | outputs
        frontier_files = next_files - frontier_files

    return connected


def layout_graph(graph: Dict, canvas_w: int = 800, canvas_h: int = 500) -> Dict:
    """Assign x,y positions to nodes using a simple layered layout.

    Files that are only inputs go left, runs in middle, files that are only
    outputs go right. Files that are both (intermediate) go between.
    """
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    # Compute depth via BFS from source files (no incoming edges)
    incoming: Dict[str, int] = {nid: 0 for nid in nodes}
    outgoing: Dict[str, list] = {nid: [] for nid in nodes}
    for e in edges:
        incoming[e["target"]] = incoming.get(e["target"], 0) + 1
        outgoing[e["source"]].append(e["target"])

    # Topological depth
    depth: Dict[str, int] = {}
    queue = [nid for nid, d in incoming.items() if d == 0]
    for nid in queue:
        depth[nid] = 0
    while queue:
        nid = queue.pop(0)
        for tgt in outgoing.get(nid, []):
            new_d = depth[nid] + 1
            if tgt not in depth or depth[tgt] < new_d:
                depth[tgt] = new_d
            incoming[tgt] -= 1
            if incoming[tgt] == 0:
                queue.append(tgt)

    # Group by depth
    columns: Dict[int, List[str]] = {}
    for nid, d in depth.items():
        columns.setdefault(d, []).append(nid)
    # Nodes not reached (cycles?) get depth 0
    for nid in nodes:
        if nid not in depth:
            columns.setdefault(0, []).append(nid)
            depth[nid] = 0

    num_cols = len(columns)
    col_width = canvas_w / max(num_cols + 1, 2)
    positions = {}
    for d, nids in columns.items():
        row_h = canvas_h / (len(nids) + 1)
        for i, nid in enumerate(nids):
            positions[nid] = {
                "x": col_width * (d + 1),
                "y": row_h * (i + 1),
            }

    return {"positions": positions, "depth": depth}

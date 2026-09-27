/* Linea dashboard — provenance graph visualization. */

let graphData = null;
let nodePositions = {};
let selectedNode = null;

const FILE_COLOR = "#3fb950";
const RUN_COLOR = "#d29922";
const RUN_FAIL_COLOR = "#f85149";

async function loadAll() {
  await Promise.all([loadStats(), loadRuns(), loadGraph()]);
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const s = await res.json();
  document.getElementById("k-runs").textContent = s.total_runs;
  document.getElementById("k-files").textContent = s.unique_files;
  document.getElementById("k-ok").textContent = s.successful;
  document.getElementById("k-fail").textContent = s.failed;
}

async function loadRuns() {
  const res = await fetch("/api/runs?limit=50");
  const runs = await res.json();
  const list = document.getElementById("run-list");
  list.innerHTML = "";
  for (const r of runs) {
    const item = document.createElement("div");
    item.className = "run-item";
    item.dataset.rid = r.id;
    const ok = r.exit_code === 0;
    item.innerHTML = `
      <span class="status ${ok ? "ok" : "fail"}"></span>
      <span class="rid">${r.id.substring(4, 20)}</span>
      <span class="cmd">${esc(r.command)}</span>
      <span class="dur">${r.duration_ms}ms</span>
    `;
    item.onclick = () => selectRun(r.id);
    list.appendChild(item);
  }
}

async function loadGraph() {
  const res = await fetch("/api/graph?max_runs=50");
  graphData = await res.json();
  computeLayout();
  drawGraph();
}

function computeLayout() {
  const nodes = graphData.nodes;
  const edges = graphData.edges;

  // Compute depth via topological sort
  const incoming = {};
  const outgoing = {};
  for (const n of nodes) { incoming[n.id] = 0; outgoing[n.id] = []; }
  for (const e of edges) {
    incoming[e.target] = (incoming[e.target] || 0) + 1;
    (outgoing[e.source] = outgoing[e.source] || []).push(e.target);
  }

  const depth = {};
  const queue = [];
  for (const nid in incoming) {
    if (incoming[nid] === 0) { depth[nid] = 0; queue.push(nid); }
  }
  while (queue.length) {
    const nid = queue.shift();
    for (const tgt of (outgoing[nid] || [])) {
      const nd = (depth[nid] || 0) + 1;
      if (!(tgt in depth) || depth[tgt] < nd) depth[tgt] = nd;
      incoming[tgt]--;
      if (incoming[tgt] === 0) queue.push(tgt);
    }
  }
  for (const n of nodes) {
    if (!(n.id in depth)) depth[n.id] = 0;
  }

  const columns = {};
  for (const n of nodes) {
    const d = depth[n.id];
    if (!columns[d]) columns[d] = [];
    columns[d].push(n.id);
  }

  const nodeW = 140, nodeH = 40, hGap = 60, vGap = 16, padX = 30, padY = 30;
  const numCols = Object.keys(columns).length;
  const colW = nodeW + hGap;
  const totalW = padX * 2 + numCols * colW;
  const maxRows = Math.max(...Object.values(columns).map(c => c.length));
  const totalH = padY * 2 + maxRows * (nodeH + vGap);

  const canvas = document.getElementById("graph-canvas");
  canvas.style.width = totalW + "px";
  canvas.style.height = totalH + "px";

  nodePositions = {};
  for (const d in columns) {
    const colNodes = columns[d];
    const colH = colNodes.length * (nodeH + vGap);
    const startY = (totalH - colH) / 2 + nodeH / 2;
    colNodes.forEach((nid, i) => {
      nodePositions[nid] = {
        x: padX + parseInt(d) * colW + nodeW / 2,
        y: startY + i * (nodeH + vGap),
        w: nodeW, h: nodeH,
      };
    });
  }
}

function drawGraph() {
  const canvas = document.getElementById("graph-canvas");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;
  ctx.clearRect(0, 0, W, H);

  const nodeMap = {};
  for (const n of graphData.nodes) nodeMap[n.id] = n;

  // edges
  for (const e of graphData.edges) {
    const from = nodePositions[e.source];
    const to = nodePositions[e.target];
    if (!from || !to) continue;
    const isOutput = e.type === "output";
    ctx.strokeStyle = isOutput ? "rgba(63,185,80,0.4)" : "rgba(88,166,255,0.4)";
    ctx.lineWidth = 1.5;
    drawEdge(ctx, from.x + from.w / 2, from.y, to.x - to.w / 2, to.y);
  }

  // nodes
  for (const n of graphData.nodes) {
    const pos = nodePositions[n.id];
    if (!pos) continue;
    const isFile = n.type === "file";
    const color = isFile ? FILE_COLOR : (n.exit_code === 0 ? RUN_COLOR : RUN_FAIL_COLOR);
    const isSelected = selectedNode === n.id;

    ctx.shadowColor = isSelected ? "rgba(88,166,255,0.4)" : "transparent";
    ctx.shadowBlur = isSelected ? 12 : 0;

    // background
    ctx.fillStyle = "#161b22";
    roundRect(ctx, pos.x - pos.w / 2, pos.y - pos.h / 2, pos.w, pos.h, 6);
    ctx.fill();

    // left border
    ctx.fillStyle = color;
    roundRect(ctx, pos.x - pos.w / 2, pos.y - pos.h / 2, 4, pos.h, 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // label
    ctx.fillStyle = "#e6edf3";
    ctx.font = "600 11px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    let label = n.label || n.id;
    if (isFile) {
      label = label.split("/").pop();
      if (label.length > 16) label = label.slice(0, 15) + "…";
    } else {
      label = (n.command || n.id).substring(0, 18);
      if (label.length >= 18) label = label.slice(0, 17) + "…";
    }
    ctx.fillText(label, pos.x + 4, pos.y - 5);

    // subtitle
    ctx.fillStyle = "#8b949e";
    ctx.font = "9px sans-serif";
    const sub = isFile ? formatSize(n.size) : `${n.duration_ms}ms`;
    ctx.fillText(sub, pos.x + 4, pos.y + 10);

    // selected border
    if (isSelected) {
      ctx.strokeStyle = "#58a6ff";
      ctx.lineWidth = 2;
      roundRect(ctx, pos.x - pos.w / 2, pos.y - pos.h / 2, pos.w, pos.h, 6);
      ctx.stroke();
    }
  }
}

function drawEdge(ctx, x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.bezierCurveTo(mx, y1, mx, y2, x2, y2);
  ctx.stroke();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function formatSize(bytes) {
  if (!bytes) return "0B";
  if (bytes < 1024) return bytes + "B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + "K";
  return (bytes / 1048576).toFixed(1) + "M";
}

// click handling
document.getElementById("graph-canvas").addEventListener("click", (e) => {
  const rect = e.target.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  for (const nid in nodePositions) {
    const p = nodePositions[nid];
    if (x >= p.x - p.w / 2 && x <= p.x + p.w / 2 &&
        y >= p.y - p.h / 2 && y <= p.y + p.h / 2) {
      selectNode(nid);
      return;
    }
  }
});

async function selectNode(nid) {
  selectedNode = nid;
  drawGraph();
  const node = graphData.nodes.find(n => n.id === nid);
  if (!node) return;

  if (node.type === "run") {
    await selectRun(node.id);
  } else {
    await selectFile(node.label);
  }
}

async function selectRun(runId) {
  selectedNode = runId;
  drawGraph();
  // highlight in list
  document.querySelectorAll(".run-item").forEach(el => {
    el.classList.toggle("selected", el.dataset.rid === runId);
  });

  const res = await fetch(`/api/run?id=${encodeURIComponent(runId)}`);
  const run = await res.json();
  document.getElementById("detail-title").textContent = "Run: " + run.id.substring(0, 24);

  let html = `
    <div class="kv"><b>command</b> ${esc(run.command)}</div>
    <div class="kv"><b>exit code</b> ${run.exit_code}</div>
    <div class="kv"><b>duration</b> ${run.duration_ms}ms</div>
    <div class="kv"><b>cwd</b> ${esc(run.cwd)}</div>
    <div class="kv"><b>started</b> ${new Date(run.started_at * 1000).toLocaleString()}</div>
  `;
  if (run.tags && run.tags.length) {
    html += `<div class="kv"><b>tags</b> ${run.tags.map(t => `<span class="run-tag">${esc(t)}</span>`).join("")}</div>`;
  }
  html += `<div class="kv"><b>inputs (${run.inputs.length})</b></div>`;
  for (const inp of run.inputs) {
    html += `<div style="margin-left:12px"><span class="file-tag">${esc(inp.path)}</span> <span style="color:var(--muted);font-size:11px">${inp.size}B sha:${(inp.sha256||'?').substring(0,8)}</span></div>`;
  }
  html += `<div class="kv"><b>outputs (${run.outputs.length})</b></div>`;
  for (const out of run.outputs) {
    html += `<div style="margin-left:12px"><span class="file-tag">${esc(out.path)}</span> <span style="color:var(--muted);font-size:11px">${out.size}B sha:${(out.sha256||'?').substring(0,8)}</span></div>`;
  }
  if (run.stdout) {
    html += `<div class="kv"><b>stdout</b></div><pre>${esc(run.stdout)}</pre>`;
  }
  if (run.stderr) {
    html += `<div class="kv"><b>stderr</b></div><pre>${esc(run.stderr)}</pre>`;
  }
  document.getElementById("detail-content").innerHTML = html;
}

async function selectFile(filepath) {
  document.getElementById("detail-title").textContent = "File: " + filepath;

  const [traceRes, impactRes] = await Promise.all([
    fetch(`/api/trace?file=${encodeURIComponent(filepath)}`),
    fetch(`/api/impact?file=${encodeURIComponent(filepath)}`),
  ]);
  const trace = await traceRes.json();
  const impact = await impactRes.json();

  let html = `<div class="kv"><b>path</b> ${esc(filepath)}</div>`;

  if (trace.produced_by) {
    html += `<div class="kv"><b>produced by</b> <span class="run-tag">${trace.produced_by.id.substring(0,20)}</span></div>`;
    html += `<div style="margin-left:12px;color:var(--muted);font-size:12px">${esc(trace.produced_by.command)}</div>`;
  } else {
    html += `<div class="kv"><b>source</b> <span style="color:var(--muted)">external / not tracked</span></div>`;
  }

  if (trace.inputs && trace.inputs.length) {
    html += `<div class="kv"><b>depends on (${trace.inputs.length})</b></div>`;
    for (const inp of trace.inputs) {
      html += `<div style="margin-left:12px"><span class="file-tag">${esc(inp.file)}</span></div>`;
    }
  }

  const downstream = [];
  function collect(node) {
    for (const c of (node.consumed_by || [])) {
      for (const o of (c.outputs || [])) {
        downstream.push(o.file);
        collect(o);
      }
    }
  }
  collect(impact);
  if (downstream.length) {
    html += `<div class="kv"><b>downstream (${downstream.length})</b></div>`;
    for (const f of [...new Set(downstream)]) {
      html += `<div style="margin-left:12px"><span class="file-tag">${esc(f)}</span></div>`;
    }
  }

  document.getElementById("detail-content").innerHTML = html;
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

window.addEventListener("resize", () => {
  if (graphData) { computeLayout(); drawGraph(); }
});

loadAll();

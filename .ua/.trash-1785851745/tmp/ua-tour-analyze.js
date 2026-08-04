#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function fail(msg) {
  console.error("ERROR: " + msg);
  process.exit(1);
}

const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  fail("Usage: node ua-tour-analyze.js <input.json> <output.json>");
}

let raw;
try {
  raw = fs.readFileSync(inputPath, "utf8");
} catch (e) {
  fail("Could not read input file: " + e.message);
}

let data;
try {
  data = JSON.parse(raw);
} catch (e) {
  fail("Invalid JSON input: " + e.message);
}

const nodes = Array.isArray(data.nodes) ? data.nodes : [];
const edges = Array.isArray(data.edges) ? data.edges : [];
const layers = Array.isArray(data.layers) ? data.layers : [];

const nodeById = new Map();
for (const n of nodes) {
  nodeById.set(n.id, n);
}

// Filter edges to only those with valid source/target
const validEdges = edges.filter(
  (e) => nodeById.has(e.source) && nodeById.has(e.target),
);

// ---------- A & B: Fan-in / Fan-out ----------
const fanIn = new Map();
const fanOut = new Map();
for (const n of nodes) {
  fanIn.set(n.id, 0);
  fanOut.set(n.id, 0);
}
for (const e of validEdges) {
  fanOut.set(e.source, (fanOut.get(e.source) || 0) + 1);
  fanIn.set(e.target, (fanIn.get(e.target) || 0) + 1);
}

const fanInRanking = nodes
  .map((n) => ({ id: n.id, fanIn: fanIn.get(n.id) || 0, name: n.name }))
  .sort((a, b) => b.fanIn - a.fanIn)
  .slice(0, 20);

const fanOutRanking = nodes
  .map((n) => ({ id: n.id, fanOut: fanOut.get(n.id) || 0, name: n.name }))
  .sort((a, b) => b.fanOut - a.fanOut)
  .slice(0, 20);

// ---------- C: Entry point candidates ----------
const ENTRY_FILENAMES = new Set([
  "index.ts",
  "index.js",
  "main.ts",
  "main.js",
  "app.ts",
  "app.js",
  "server.ts",
  "server.js",
  "mod.rs",
  "main.go",
  "main.py",
  "main.rs",
  "manage.py",
  "app.py",
  "wsgi.py",
  "asgi.py",
  "run.py",
  "__main__.py",
  "Application.java",
  "Main.java",
  "Program.cs",
  "config.ru",
  "index.php",
  "App.swift",
  "Application.kt",
  "main.cpp",
  "main.c",
]);

const fanOutValues = nodes
  .map((n) => fanOut.get(n.id) || 0)
  .sort((a, b) => a - b);
const fanInValues = nodes
  .map((n) => fanIn.get(n.id) || 0)
  .sort((a, b) => a - b);

function percentileThreshold(sortedValues, percentileFromTop) {
  if (sortedValues.length === 0) return 0;
  const idx = Math.max(
    0,
    Math.floor(sortedValues.length * (1 - percentileFromTop)),
  );
  return sortedValues[idx];
}

const fanOutTop10Threshold = percentileThreshold(fanOutValues, 0.1);
const fanInBottom25Threshold = (sorted) =>
  sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.25))];
const fanInBottomThreshold = fanInBottom25Threshold(fanInValues);

function depthFromRoot(filePath) {
  if (!filePath) return 99;
  const parts = filePath.split("/").filter(Boolean);
  return parts.length; // 1 = root file, 2 = one level deep
}

const entryScores = [];
for (const n of nodes) {
  let score = 0;
  const fp = n.filePath || "";
  const baseName = path.basename(fp || n.name || "");

  if (n.type === "document") {
    const depth = depthFromRoot(fp);
    if (baseName.toLowerCase() === "readme.md" && depth <= 1) {
      score += 5;
    } else if (baseName.toLowerCase().endsWith(".md") && depth <= 1) {
      score += 2;
    }
  } else if (n.type === "file") {
    if (ENTRY_FILENAMES.has(baseName)) {
      score += 3;
    }
    const depth = depthFromRoot(fp);
    if (depth <= 2) {
      score += 1;
    }
    const fo = fanOut.get(n.id) || 0;
    const fi = fanIn.get(n.id) || 0;
    if (fo >= fanOutTop10Threshold && fo > 0) {
      score += 1;
    }
    if (fi <= fanInBottomThreshold) {
      score += 1;
    }
  }

  if (score > 0) {
    entryScores.push({
      id: n.id,
      score,
      name: n.name,
      summary: n.summary || "",
    });
  }
}

entryScores.sort((a, b) => b.score - a.score);
const entryPointCandidates = entryScores.slice(0, 5);

// ---------- D: BFS from top code entry point ----------
// Skip documentation nodes for BFS start; find top-scoring 'file' type candidate
function findTopCodeEntry() {
  for (const cand of entryScores) {
    const n = nodeById.get(cand.id);
    if (n && n.type !== "document") {
      return cand.id;
    }
  }
  // fallback: any file node with app.py/main.py etc, else first file node
  for (const n of nodes) {
    if (
      n.type === "file" &&
      ENTRY_FILENAMES.has(path.basename(n.filePath || n.name || ""))
    ) {
      return n.id;
    }
  }
  const firstFile = nodes.find((n) => n.type === "file");
  return firstFile ? firstFile.id : nodes[0] ? nodes[0].id : null;
}

const bfsStart = findTopCodeEntry();

const adjacency = new Map();
for (const n of nodes) adjacency.set(n.id, []);
for (const e of validEdges) {
  if (e.type === "imports" || e.type === "calls") {
    adjacency.get(e.source).push(e.target);
  }
}

const bfsOrder = [];
const depthMap = {};
const byDepth = {};

if (bfsStart) {
  const visited = new Set([bfsStart]);
  const queue = [[bfsStart, 0]];
  while (queue.length > 0) {
    const [cur, depth] = queue.shift();
    bfsOrder.push(cur);
    depthMap[cur] = depth;
    if (!byDepth[depth]) byDepth[depth] = [];
    byDepth[depth].push(cur);
    const neighbors = adjacency.get(cur) || [];
    for (const nb of neighbors) {
      if (!visited.has(nb)) {
        visited.add(nb);
        queue.push([nb, depth + 1]);
      }
    }
  }
}

// ---------- E: Non-code file inventory ----------
const nonCodeFiles = {
  documentation: [],
  infrastructure: [],
  data: [],
  config: [],
};

for (const n of nodes) {
  const entry = { id: n.id, name: n.name, summary: n.summary || "" };
  if (n.type === "document") {
    nonCodeFiles.documentation.push(entry);
  } else if (
    n.type === "service" ||
    n.type === "pipeline" ||
    n.type === "resource"
  ) {
    nonCodeFiles.infrastructure.push({ ...entry, type: n.type });
  } else if (
    n.type === "table" ||
    n.type === "schema" ||
    n.type === "endpoint"
  ) {
    nonCodeFiles.data.push({ ...entry, type: n.type });
  } else if (n.type === "config") {
    nonCodeFiles.config.push(entry);
  }
}

// ---------- F: Tightly coupled clusters ----------
const edgeKey = (a, b) => a + "||" + b;
const edgeSet = new Set(
  validEdges
    .filter((e) => e.type === "imports" || e.type === "calls")
    .map((e) => edgeKey(e.source, e.target)),
);

const bidirectionalPairs = [];
for (const e of validEdges) {
  if (e.type !== "imports" && e.type !== "calls") continue;
  if (e.source === e.target) continue;
  if (edgeSet.has(edgeKey(e.target, e.source))) {
    const pairKey = [e.source, e.target].sort().join("||");
    bidirectionalPairs.push(pairKey);
  }
}
const uniquePairs = Array.from(new Set(bidirectionalPairs)).map((p) =>
  p.split("||"),
);

// Union-find to merge overlapping pairs into clusters, then expand
const parent = new Map();
function find(x) {
  if (!parent.has(x)) parent.set(x, x);
  let root = x;
  while (parent.get(root) !== root) root = parent.get(root);
  parent.set(x, root);
  return root;
}
function union(a, b) {
  const ra = find(a),
    rb = find(b);
  if (ra !== rb) parent.set(ra, rb);
}

for (const [a, b] of uniquePairs) {
  find(a);
  find(b);
  union(a, b);
}

const clusterMap = new Map();
for (const [a] of uniquePairs) {
  const root = find(a);
  if (!clusterMap.has(root)) clusterMap.set(root, new Set());
}
for (const [a, b] of uniquePairs) {
  const root = find(a);
  clusterMap.get(root).add(a);
  clusterMap.get(root).add(b);
}

// Expand: add nodes connecting to 2+ existing cluster members (edges either direction, imports/calls)
const allRelEdges = validEdges.filter(
  (e) => e.type === "imports" || e.type === "calls",
);
for (const [root, members] of clusterMap.entries()) {
  if (members.size >= 5) continue;
  let changed = true;
  while (changed && members.size < 5) {
    changed = false;
    const connectionCount = new Map();
    for (const e of allRelEdges) {
      if (members.has(e.source) && !members.has(e.target)) {
        connectionCount.set(e.target, (connectionCount.get(e.target) || 0) + 1);
      } else if (members.has(e.target) && !members.has(e.source)) {
        connectionCount.set(e.source, (connectionCount.get(e.source) || 0) + 1);
      }
    }
    let bestNode = null,
      bestCount = 0;
    for (const [node, count] of connectionCount.entries()) {
      if (count >= 2 && count > bestCount) {
        bestNode = node;
        bestCount = count;
      }
    }
    if (bestNode && members.size < 5) {
      members.add(bestNode);
      changed = true;
    }
  }
}

function edgeCountWithin(members) {
  let count = 0;
  for (const e of allRelEdges) {
    if (members.has(e.source) && members.has(e.target)) count++;
  }
  return count;
}

let clusters = Array.from(clusterMap.values())
  .filter((members) => members.size >= 2 && members.size <= 5)
  .map((members) => ({
    nodes: Array.from(members),
    edgeCount: edgeCountWithin(members),
  }))
  .sort((a, b) => b.edgeCount - a.edgeCount)
  .slice(0, 10);

// ---------- G: Layer list ----------
const layersOut = {
  count: layers.length,
  list: layers.map((l) => ({
    id: l.id,
    name: l.name,
    description: l.description || "",
  })),
};

// ---------- H: Node summary index ----------
const nodeSummaryIndex = {};
for (const n of nodes) {
  nodeSummaryIndex[n.id] = {
    name: n.name,
    type: n.type,
    summary: n.summary || "",
  };
}

// ---------- Output ----------
const result = {
  scriptCompleted: true,
  entryPointCandidates,
  fanInRanking,
  fanOutRanking,
  bfsTraversal: {
    startNode: bfsStart,
    order: bfsOrder,
    depthMap,
    byDepth,
  },
  nonCodeFiles,
  clusters,
  layers: layersOut,
  nodeSummaryIndex,
  totalNodes: nodes.length,
  totalEdges: validEdges.length,
};

try {
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
} catch (e) {
  fail("Could not write output file: " + e.message);
}

console.log("Analysis complete. Output written to " + outputPath);
process.exit(0);

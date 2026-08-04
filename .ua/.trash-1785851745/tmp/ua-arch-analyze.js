#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function main() {
  const inputPath = process.argv[2];
  const outputPath = process.argv[3];
  if (!inputPath || !outputPath) {
    console.error("Usage: node ua-arch-analyze.js <input.json> <output.json>");
    process.exit(1);
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  } catch (e) {
    console.error("Failed to read/parse input JSON: " + e.message);
    process.exit(1);
  }

  const fileNodes = raw.fileNodes || [];
  const importEdges = raw.importEdges || [];
  const allEdges = raw.allEdges || [];

  const nodeById = new Map();
  for (const n of fileNodes) nodeById.set(n.id, n);

  // ---------- A. Directory Grouping ----------
  function dirOf(fp) {
    if (!fp) return "";
    const idx = fp.lastIndexOf("/");
    return idx === -1 ? "" : fp.substring(0, idx);
  }

  const paths = fileNodes
    .map((n) => n.filePath || n.name || "")
    .filter(Boolean);

  function commonPrefix(strs) {
    if (strs.length === 0) return "";
    const splitPaths = strs.map((s) => s.split("/"));
    const minLen = Math.min(...splitPaths.map((p) => p.length));
    const prefixParts = [];
    for (let i = 0; i < minLen - 1; i++) {
      const seg = splitPaths[0][i];
      if (splitPaths.every((p) => p[i] === seg)) {
        prefixParts.push(seg);
      } else {
        break;
      }
    }
    return prefixParts.length ? prefixParts.join("/") + "/" : "";
  }

  const prefix = commonPrefix(paths);

  function firstSegmentAfterPrefix(fp) {
    let rest = fp;
    if (prefix && fp.startsWith(prefix)) {
      rest = fp.substring(prefix.length);
    }
    const parts = rest.split("/");
    if (parts.length > 1) {
      return parts[0];
    }
    // flat file directly under prefix (or root) - group by extension pattern
    const fname = parts[0];
    return classifyFlatFile(fname);
  }

  function classifyFlatFile(fname) {
    if (
      /\.(test|spec)\./.test(fname) ||
      /^test_/.test(fname) ||
      /_test\.go$/.test(fname)
    )
      return "test";
    if (/\.config\./.test(fname) || /config/i.test(fname)) return "config";
    const ext = fname.includes(".")
      ? fname.substring(fname.lastIndexOf(".") + 1)
      : "noext";
    return ext || "root";
  }

  const directoryGroups = {};
  for (const n of fileNodes) {
    const fp = n.filePath || n.name || n.id;
    const group = firstSegmentAfterPrefix(fp) || "root";
    if (!directoryGroups[group]) directoryGroups[group] = [];
    directoryGroups[group].push(n.id);
  }

  // ---------- B. Node Type Grouping ----------
  const nodeTypeGroups = {};
  for (const n of fileNodes) {
    const t = n.type || "unknown";
    if (!nodeTypeGroups[t]) nodeTypeGroups[t] = [];
    nodeTypeGroups[t].push(n.id);
  }

  // ---------- C. Import Adjacency Matrix ----------
  const fanOut = {};
  const fanIn = {};
  for (const n of fileNodes) {
    fanOut[n.id] = 0;
    fanIn[n.id] = 0;
  }
  const groupOfId = {};
  for (const [g, ids] of Object.entries(directoryGroups)) {
    for (const id of ids) groupOfId[id] = g;
  }

  for (const e of importEdges) {
    if (fanOut.hasOwnProperty(e.source)) fanOut[e.source]++;
    if (fanIn.hasOwnProperty(e.target)) fanIn[e.target]++;
  }

  // ---------- D. Cross-Category Dependency Analysis ----------
  const crossCategoryMap = new Map();
  for (const e of allEdges) {
    const s = nodeById.get(e.source);
    const t = nodeById.get(e.target);
    if (!s || !t) continue;
    if (s.type === t.type) continue; // cross-category only per spec examples; but keep general
    const key = `${s.type}|${t.type}|${e.type}`;
    crossCategoryMap.set(key, (crossCategoryMap.get(key) || 0) + 1);
  }
  const crossCategoryEdges = [];
  for (const [key, count] of crossCategoryMap.entries()) {
    const [fromType, toType, edgeType] = key.split("|");
    crossCategoryEdges.push({ fromType, toType, edgeType, count });
  }

  // ---------- E. Inter-Group Import Frequency ----------
  const interGroupMap = new Map();
  for (const e of importEdges) {
    const g1 = groupOfId[e.source];
    const g2 = groupOfId[e.target];
    if (!g1 || !g2 || g1 === g2) continue;
    const key = `${g1}|${g2}`;
    interGroupMap.set(key, (interGroupMap.get(key) || 0) + 1);
  }
  const interGroupImports = [];
  for (const [key, count] of interGroupMap.entries()) {
    const [from, to] = key.split("|");
    interGroupImports.push({ from, to, count });
  }

  // ---------- F. Intra-Group Import Density ----------
  const intraGroupDensity = {};
  for (const g of Object.keys(directoryGroups)) {
    let internal = 0;
    let total = 0;
    for (const e of importEdges) {
      const g1 = groupOfId[e.source];
      const g2 = groupOfId[e.target];
      if (g1 === g || g2 === g) {
        total++;
        if (g1 === g && g2 === g) internal++;
      }
    }
    intraGroupDensity[g] = {
      internalEdges: internal,
      totalEdges: total,
      density: total > 0 ? internal / total : 0,
    };
  }

  // ---------- G. Directory Pattern Matching ----------
  const dirPatternTable = [
    {
      pats: ["routes", "api", "controllers", "endpoints", "handlers"],
      label: "api",
    },
    { pats: ["services", "core", "lib", "domain", "logic"], label: "service" },
    {
      pats: ["models", "db", "data", "persistence", "repository", "entities"],
      label: "data",
    },
    {
      pats: ["components", "views", "pages", "ui", "layouts", "screens"],
      label: "ui",
    },
    {
      pats: ["middleware", "plugins", "interceptors", "guards"],
      label: "middleware",
    },
    {
      pats: ["utils", "helpers", "common", "shared", "tools"],
      label: "utility",
    },
    { pats: ["config", "constants", "env", "settings"], label: "config" },
    { pats: ["__tests__", "test", "tests", "spec", "specs"], label: "test" },
    {
      pats: ["types", "interfaces", "schemas", "contracts", "dtos"],
      label: "types",
    },
    { pats: ["hooks"], label: "hooks" },
    {
      pats: ["store", "state", "reducers", "actions", "slices"],
      label: "state",
    },
    { pats: ["assets", "static", "public"], label: "assets" },
    { pats: ["migrations"], label: "data" },
    { pats: ["management", "commands"], label: "config" },
    { pats: ["templatetags"], label: "utility" },
    { pats: ["signals"], label: "service" },
    { pats: ["serializers"], label: "api" },
    { pats: ["cmd"], label: "entry" },
    { pats: ["internal"], label: "service" },
    { pats: ["pkg"], label: "utility" },
    { pats: ["dto", "request", "response"], label: "types" },
    { pats: ["entity"], label: "data" },
    { pats: ["controller"], label: "api" },
    { pats: ["routers"], label: "api" },
    { pats: ["composables"], label: "service" },
    { pats: ["blueprints"], label: "api" },
    { pats: ["mailers", "jobs", "channels"], label: "service" },
    { pats: ["bin"], label: "entry" },
    { pats: ["docs", "documentation", "wiki"], label: "documentation" },
    {
      pats: ["deploy", "deployment", "infra", "infrastructure"],
      label: "infrastructure",
    },
    { pats: [".github", ".gitlab", ".circleci"], label: "ci-cd" },
    { pats: ["k8s", "kubernetes", "helm", "charts"], label: "infrastructure" },
    { pats: ["terraform", "tf"], label: "infrastructure" },
    { pats: ["docker"], label: "infrastructure" },
    { pats: ["sql", "database", "schema"], label: "data" },
  ];

  function matchDirPattern(dirName) {
    const lower = (dirName || "").toLowerCase();
    for (const row of dirPatternTable) {
      if (row.pats.includes(lower)) return row.label;
    }
    return null;
  }

  const patternMatches = {};
  for (const g of Object.keys(directoryGroups)) {
    const m = matchDirPattern(g);
    if (m) patternMatches[g] = m;
  }

  // File-level patterns
  function matchFilePattern(n) {
    const fp = n.filePath || n.name || "";
    const base = path.basename(fp);
    if (
      /\.(test|spec)\./.test(base) ||
      /^test_/.test(base) ||
      /_test\.go$/.test(base) ||
      /Test\.java$/.test(base) ||
      /_spec\.rb$/.test(base) ||
      /Test\.php$/.test(base) ||
      /Tests\.cs$/.test(base)
    ) {
      return "test";
    }
    if (/\.d\.ts$/.test(base)) return "types";
    if (base === "index.ts" || base === "index.js" || base === "__init__.py")
      return "entry";
    if (base === "manage.py") return "entry";
    if (base === "wsgi.py" || base === "asgi.py") return "config";
    if (base === "main.go" && /cmd\//.test(fp)) return "entry";
    if ((base === "main.rs" || base === "lib.rs") && /^src\//.test(fp))
      return "entry";
    if (base === "Application.java" || base === "Program.cs") return "entry";
    if (base === "config.ru") return "entry";
    if (
      [
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "composer.json",
      ].includes(base)
    )
      return "config";
    if (base === "Dockerfile" || /^docker-compose\./.test(base))
      return "infrastructure";
    if (/\.tf$/.test(base) || /\.tfvars$/.test(base)) return "infrastructure";
    if (
      /^\.github\/workflows\//.test(fp) ||
      base === ".gitlab-ci.yml" ||
      base === "Jenkinsfile"
    )
      return "ci-cd";
    if (/\.sql$/.test(base)) return "data";
    if (/\.(graphql|gql|proto)$/.test(base)) return "types";
    if (/\.(md|rst)$/.test(base)) return "documentation";
    if (base === "Makefile") return "infrastructure";
    return null;
  }

  const filePatternMatches = {};
  for (const n of fileNodes) {
    const m = matchFilePattern(n);
    if (m) filePatternMatches[n.id] = m;
  }

  // ---------- H. Deployment Topology Detection ----------
  const infraFiles = [];
  let hasDockerfile = false;
  let hasCompose = false;
  let hasK8s = false;
  let hasTerraform = false;
  let hasCI = false;
  for (const n of fileNodes) {
    const fp = n.filePath || n.name || "";
    const base = path.basename(fp);
    if (base === "Dockerfile" || /^Dockerfile\./.test(base)) {
      hasDockerfile = true;
      infraFiles.push(fp);
    } else if (/^docker-compose/.test(base)) {
      hasCompose = true;
      infraFiles.push(fp);
    } else if (/\.tf$/.test(base) || /\.tfvars$/.test(base)) {
      hasTerraform = true;
      infraFiles.push(fp);
    } else if (
      /^\.github\/workflows\//.test(fp) ||
      base === ".gitlab-ci.yml" ||
      base === "Jenkinsfile" ||
      n.type === "pipeline"
    ) {
      hasCI = true;
      infraFiles.push(fp);
    } else if (/k8s|kubernetes|helm/i.test(fp)) {
      hasK8s = true;
      infraFiles.push(fp);
    }
  }

  const deploymentTopology = {
    hasDockerfile,
    hasCompose,
    hasK8s,
    hasTerraform,
    hasCI,
    infraFiles,
  };

  // ---------- I. Data Pipeline Detection ----------
  const schemaFiles = [];
  const migrationFiles = [];
  const dataModelFiles = [];
  const apiHandlerFiles = [];
  for (const n of fileNodes) {
    const fp = n.filePath || n.name || "";
    if (
      /\.sql$/.test(fp) ||
      /\.(graphql|gql|proto)$/.test(fp) ||
      n.type === "schema"
    )
      schemaFiles.push(fp);
    if (/migrations\//.test(fp)) migrationFiles.push(fp);
    if (/models\//.test(fp) || n.type === "table") dataModelFiles.push(fp);
    if (/routes\//.test(fp) || n.type === "endpoint") apiHandlerFiles.push(fp);
  }

  const dataPipeline = {
    schemaFiles,
    migrationFiles,
    dataModelFiles,
    apiHandlerFiles,
  };

  // ---------- J. Documentation Coverage ----------
  const docFilePaths = fileNodes
    .filter((n) => n.type === "document")
    .map((n) => n.filePath || n.name || "");
  let groupsWithDocs = 0;
  const undocumentedGroups = [];
  const groupNames = Object.keys(directoryGroups);
  for (const g of groupNames) {
    const hasReadme = directoryGroups[g].some((id) => {
      const n = nodeById.get(id);
      const base = path.basename(n.filePath || n.name || "");
      return /^README/i.test(base);
    });
    const referencedByDocs = docFilePaths.some((dfp) =>
      dfp.toLowerCase().includes(g.toLowerCase()),
    );
    if (hasReadme || referencedByDocs) {
      groupsWithDocs++;
    } else {
      undocumentedGroups.push(g);
    }
  }
  const totalGroups = groupNames.length;
  const docCoverage = {
    groupsWithDocs,
    totalGroups,
    coverageRatio:
      totalGroups > 0 ? +(groupsWithDocs / totalGroups).toFixed(2) : 0,
    undocumentedGroups,
  };

  // ---------- K. Dependency Direction ----------
  const pairSeen = new Set();
  const dependencyDirection = [];
  for (const { from, to, count } of interGroupImports) {
    const key = [from, to].sort().join("|");
    if (pairSeen.has(key)) continue;
    pairSeen.add(key);
    const reverse = interGroupImports.find(
      (x) => x.from === to && x.to === from,
    );
    const reverseCount = reverse ? reverse.count : 0;
    if (count > reverseCount) {
      dependencyDirection.push({ dependent: from, dependsOn: to });
    } else if (reverseCount > count) {
      dependencyDirection.push({ dependent: to, dependsOn: from });
    }
  }

  // ---------- fileStats ----------
  const filesPerGroup = {};
  for (const [g, ids] of Object.entries(directoryGroups))
    filesPerGroup[g] = ids.length;
  const nodeTypeCounts = {};
  for (const [t, ids] of Object.entries(nodeTypeGroups))
    nodeTypeCounts[t] = ids.length;

  const fileStats = {
    totalFileNodes: fileNodes.length,
    filesPerGroup,
    nodeTypeCounts,
  };

  const result = {
    scriptCompleted: true,
    directoryGroups,
    nodeTypeGroups,
    crossCategoryEdges,
    interGroupImports,
    intraGroupDensity,
    patternMatches,
    filePatternMatches,
    deploymentTopology,
    dataPipeline,
    docCoverage,
    dependencyDirection,
    fileStats,
    fileFanIn: fanIn,
    fileFanOut: fanOut,
  };

  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  process.exit(0);
}

try {
  main();
} catch (e) {
  console.error("Fatal error: " + (e && e.stack ? e.stack : e));
  process.exit(1);
}

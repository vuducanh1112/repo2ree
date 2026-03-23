import React, { useEffect, useMemo, useRef, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────────
interface Level {
  n: number;
  label: string;
  color: string;
  bg: string;
  ink: string;
  short: string;
  desc: string;
  problem: string | null;
  fix: string | null;
}

interface ServiceParam {
  key: string;
  label: string;
  type: "bool" | "select" | "text";
  default: boolean | string;
  hint: string;
  options?: string[];
}

interface ServiceRequire {
  field: keyof Ree;
  label: string;
}

interface ServiceBadge {
  label: string;
  color: string;
  bg: string;
}

interface Service {
  key: string;
  label: string;
  IC: (s?: number) => JSX.Element;
  color: string;
  badge: ServiceBadge;
  desc: string;
  requires: ServiceRequire[];
  params: ServiceParam[];
}

interface ToastState {
  message: string;
  type: "success" | "error" | "info";
}

type StepState = "idle" | "loading" | "done";

interface CablePoint {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface Cable extends CablePoint {
  color: string;
  shadow: string;
  connected: boolean;
}

interface CableGeo {
  cables: Cable[];
  decoCables: CablePoint[];
  w: number;
  h: number;
}

interface Ree {
  name: string;
  swhid: string;
  origin_url: string;
  source_type: "" | "git" | "svn" | "hg" | "cvs" | "bzr" | "tarball";
  detected_dependencies?: string;
  repro_level?: string;
  runtime: string;
  build_runtime_script: string;
  sbom: string;
  activation_script: string;
  hardware_description: Record<string, string>;
  zenodo_doi?: string;
  dataverse_doi?: string;
  _evalLevel?: number;
  _sealedAt?: string;
  _sealHash?: string;
  _sourceIncluded?: boolean;
  _sourceAvailable?: boolean;
  _sourceAcquiredBy?: "download" | "upload";
  _runtimeIncluded?: boolean;
  _uploadedArchive?: string;
  _sourceSnapshotArchive?: string;
  _sourceSnapshotCapturedAt?: string;
}

interface FileTreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  content?: string;
  tag?: string;
  children?: FileTreeNode[];
}

interface SourceUploadCommit {
  mode: "archive";
  archiveName?: string;
}

interface ReeFile {
  id: string;
  name: string;
  type: "file";
  tag?: string;
  content?: string;
}

type LogLineType = "info" | "ok" | "warn" | "err" | "out";

interface LogLine {
  type: LogLineType;
  msg: string;
}

interface LogEntry {
  lines: LogLine[];
  ts: string;
}

type PinStatus = "exact" | "range" | "none";

interface DepPackage {
  name: string;
  version: string | null;
  raw: string;
  pinned: PinStatus;
  dev?: boolean;
  ecosystem?: string;
}

interface DepGroup {
  file: string;
  path: string;
  ecosystem: string;
  packages: DepPackage[];
}

type Badges = Record<string, boolean>;
type Timestamps = Record<string, string>;
type ActionStates = Record<string, "loading" | "done">;
type ServiceLogs = Record<string, LogEntry>;
type ServiceParams = Record<string, Record<string, unknown>>;

// ── ZIP builder ────────────────────────────────────────────────────────────────
function _zipU32(n: number): number[] {
  return [n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >> 24) & 0xff];
}
function _zipU16(n: number): number[] {
  return [n & 0xff, (n >> 8) & 0xff];
}
function _crc32(data: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    c ^= data[i];
    for (let j = 0; j < 8; j++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
  }
  return (c ^ 0xffffffff) >>> 0;
}
interface ZipEntry {
  path: string;
  data: Uint8Array;
}
function buildZipBlob(entries: ZipEntry[]): Blob {
  const enc = new TextEncoder();
  const localParts: number[] = [];
  const central: number[] = [];
  const offsets: number[] = [];
  let off = 0;
  for (const e of entries) {
    const name = enc.encode(e.path);
    const crc = _crc32(e.data);
    const sz = e.data.length;
    offsets.push(off);
    const local = [
      ..._zipU32(0x04034b50),
      ..._zipU16(20),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(crc),
      ..._zipU32(sz),
      ..._zipU32(sz),
      ..._zipU16(name.length),
      ..._zipU16(0),
      ...Array.from(name),
      ...Array.from(e.data),
    ];
    localParts.push(...local);
    off += local.length;
  }
  for (let i = 0; i < entries.length; i++) {
    const name = enc.encode(entries[i].path);
    const crc = _crc32(entries[i].data);
    const sz = entries[i].data.length;
    central.push(
      ..._zipU32(0x02014b50),
      ..._zipU16(20),
      ..._zipU16(20),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(crc),
      ..._zipU32(sz),
      ..._zipU32(sz),
      ..._zipU16(name.length),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(0),
      ..._zipU32(offsets[i]),
      ...Array.from(name),
    );
  }
  const cdOff = off;
  const eocd = [
    ..._zipU32(0x06054b50),
    ..._zipU16(0),
    ..._zipU16(0),
    ..._zipU16(entries.length),
    ..._zipU16(entries.length),
    ..._zipU32(central.length),
    ..._zipU32(cdOff),
    ..._zipU16(0),
  ];
  return new Blob([new Uint8Array([...localParts, ...central, ...eocd])], {
    type: "application/zip",
  });
}

function findVirtualFileByName(nodes: FileTreeNode[], name: string): FileTreeNode | null {
  if (!name) return null;
  const base = name.split("/").pop();
  function walk(items: FileTreeNode[]): FileTreeNode | null {
    for (const item of items) {
      if (item.type === "file" && item.name === base) return item;
      if (item.children) {
        const found = walk(item.children);
        if (found) return found;
      }
    }
    return null;
  }
  return walk(nodes || []);
}

function normalizeSnapshotArchiveName(rawName: string): string {
  const trimmed = (rawName || "").trim();
  if (!trimmed) return "source.tar.gz";
  if (/\.tar\.gz$/i.test(trimmed)) return trimmed;
  if (/\.tgz$/i.test(trimmed)) return trimmed.replace(/\.tgz$/i, ".tar.gz");
  const stem = trimmed.replace(/\.(zip|tar|tar\.bz2|tar\.xz|tar\.zst|jar)$/i, "");
  return `${stem || "source"}.tar.gz`;
}

function listTreeFiles(
  nodes: FileTreeNode[],
  prefix = "",
): Array<{ path: string; content: string }> {
  let files: Array<{ path: string; content: string }> = [];
  for (const node of nodes || []) {
    const path = prefix ? `${prefix}${node.name}` : node.name;
    if (node.type === "file") {
      files.push({ path, content: node.content ?? "" });
    } else if (node.children) {
      files = files.concat(listTreeFiles(node.children, `${path}/`));
    }
  }
  return files;
}

function normalizeWorkspacePath(path: string): string {
  return (path || "").replace(/^\/+/, "").trim();
}

function findTreeFileBySelectedPath(
  files: Array<{ path: string; content: string }>,
  selectedPath: string,
): { path: string; content: string } | null {
  const normalized = normalizeWorkspacePath(selectedPath);
  if (!normalized) return null;
  const exact = files.find((f) => normalizeWorkspacePath(f.path) === normalized);
  if (exact) return exact;
  const selectedBase = normalized.split("/").pop();
  if (!selectedBase) return null;
  return (
    files.find((f) => normalizeWorkspacePath(f.path).split("/").pop() === selectedBase) || null
  );
}

function archiveWorkspacePath(path: string): string {
  return normalizeWorkspacePath(path).replace(/\.\.+/g, "_");
}

function buildSnapshotArchiveContent(
  sourceSnapshotFiles: FileTreeNode[],
  capturedAt?: string,
): string {
  const files = listTreeFiles(sourceSnapshotFiles);
  return [
    "# Immutable source snapshot",
    `captured_at=${capturedAt || new Date().toISOString()}`,
    `file_count=${files.length}`,
    "",
    ...files.flatMap((file) => [`>>> ${file.path}`, file.content, ""]),
  ].join("\n");
}

function buildCurrentReeArchiveEntries(
  ree: Ree,
  virtualFiles: FileTreeNode[],
  sourceSnapshotFiles: FileTreeNode[],
  sourceSnapshotArchiveName?: string,
): ZipEntry[] {
  const enc = new TextEncoder();
  const entries: ZipEntry[] = [];
  const workspaceFiles = listTreeFiles(virtualFiles);
  const sourcePaths = new Set(
    listTreeFiles(sourceSnapshotFiles).map((f) => normalizeWorkspacePath(f.path)),
  );

  const manifest = {
    ree_version: "1.0",
    name: ree.name || null,
    origin_url: ree.origin_url || null,
    source_type: ree.source_type || null,
    runtime: ree.runtime || null,
    build_script: ree.build_runtime_script || null,
    activation_script: ree.activation_script || null,
    sbom: ree.sbom || null,
    swhid: ree.swhid || null,
    zenodo_doi: ree.zenodo_doi || null,
    dataverse_doi: ree.dataverse_doi || null,
    hardware_description: ree.hardware_description || {},
    sealed_at: ree._sealedAt || null,
    seal_hash: ree._sealHash || null,
    eval_level: ree._evalLevel ?? 0,
    source_included: !!ree._sourceIncluded,
    source_available: !!ree._sourceAvailable,
    source_acquired_by: ree._sourceAcquiredBy || null,
    source_snapshot_archive: ree._sourceSnapshotArchive || null,
    source_snapshot_captured_at: ree._sourceSnapshotCapturedAt || null,
    runtime_included: !!ree._runtimeIncluded,
  };
  entries.push({ path: "ree/ree.json", data: enc.encode(JSON.stringify(manifest, null, 2)) });

  if (ree.sbom && ree.sbom !== "__skipped__") {
    const sbomNode = findVirtualFileByName(virtualFiles, ree.sbom);
    const sbomContent =
      sbomNode?.content ??
      JSON.stringify({ note: "SBOM not yet generated — run Generate SBOM first" }, null, 2);
    entries.push({ path: "ree/sbom.json", data: enc.encode(sbomContent) });
  }

  if (ree._runtimeIncluded && ree.runtime && ree.runtime !== "__skipped__") {
    const runtimeNode = findVirtualFileByName(virtualFiles, ree.runtime);
    const runtimeContent =
      runtimeNode?.content ??
      `# Runtime placeholder\n# ref: ${ree.runtime}\n# Enable "Build Runtime" to produce the real tarball.`;
    entries.push({ path: "ree/runtime.tar.gz", data: enc.encode(runtimeContent) });
  }

  if (ree._sourceIncluded && sourceSnapshotFiles.length > 0) {
    for (const file of listTreeFiles(sourceSnapshotFiles)) {
      entries.push({ path: `ree/source-repo/${file.path}`, data: enc.encode(file.content) });
    }

    const archiveName = normalizeSnapshotArchiveName(
      sourceSnapshotArchiveName || ree._sourceSnapshotArchive || "source-original.tar.gz",
    );
    const archiveContent = buildSnapshotArchiveContent(
      sourceSnapshotFiles,
      ree._sourceSnapshotCapturedAt,
    );
    entries.push({ path: `ree/${archiveName}`, data: enc.encode(archiveContent) });
  }

  const selectedScripts: Array<{
    key: "build_runtime_script" | "activation_script";
    path: string;
  }> = [
    { key: "build_runtime_script", path: ree.build_runtime_script || "" },
    { key: "activation_script", path: ree.activation_script || "" },
  ];

  for (const selected of selectedScripts) {
    const selectedPath = normalizeWorkspacePath(selected.path);
    if (!selectedPath) continue;
    const selectedFile = findTreeFileBySelectedPath(workspaceFiles, selectedPath);
    if (!selectedFile) continue;
    if (sourcePaths.has(normalizeWorkspacePath(selectedFile.path))) continue;
    const archivePath = archiveWorkspacePath(selectedPath);
    if (!archivePath) continue;
    const reePath = `ree/${archivePath}`;
    if (entries.some((e) => e.path === reePath)) continue;
    entries.push({ path: reePath, data: enc.encode(selectedFile.content || "") });
  }

  return entries;
}

function reeArchiveEntriesToFiles(entries: ZipEntry[]): ReeFile[] {
  const dec = new TextDecoder();
  return entries.map((entry, idx) => ({
    id: `ree-archive-${idx}`,
    name: entry.path,
    type: "file",
    tag:
      entry.path === "ree/ree.json"
        ? "Manifest"
        : entry.path === "ree/sbom.json"
          ? "SBOM"
          : entry.path === "ree/runtime.tar.gz"
            ? "Runtime"
            : entry.path.startsWith("ree/source-repo/")
              ? "Source"
              : entry.path.startsWith("ree/")
                ? "Workspace"
                : "REE",
    content: dec.decode(entry.data),
  }));
}

// ── Icons ──────────────────────────────────────────────────────────────────────
interface SvgProps {
  d: string;
  size?: number;
  fill?: string;
  sw?: number;
  title?: string;
}

const Svg = ({ d, size = 15, fill = "none", sw = 1.6, title = "icon" }: SvgProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill}
    stroke="currentColor"
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <title>{title}</title>
    <path d={d} />
  </svg>
);
const Ic = {
  folder: (s = 15) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="#f59e0b" stroke="none">
      <title>Folder</title>
      <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
    </svg>
  ),
  file: (s = 15) => (
    <Svg size={s} d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm0 0v6h6" sw={1.4} />
  ),
  chevR: (s = 15) => <Svg size={s} d="M9 18l6-6-6-6" />,
  chevD: (s = 15) => <Svg size={s} d="M6 9l6 6 6-6" />,
  download: (s = 15) => (
    <Svg size={s} d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
  ),
  upload: (s = 15) => (
    <Svg size={s} d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
  ),
  link: (s = 15) => (
    <Svg
      size={s}
      d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"
    />
  ),
  star: (s = 15) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <title>Star</title>
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  ),
  check: (s = 15) => <Svg size={s} d="M20 6L9 17l-5-5" />,
  loader: (s = 15) => (
    <Svg
      size={s}
      d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
    />
  ),
  archive: (s = 15) => <Svg size={s} d="M21 8v13H3V8M1 3h22v5H1zM10 12h4" />,
  cpu: (s = 15) => (
    <Svg
      size={s}
      d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"
    />
  ),
  shield: (s = 15) => <Svg size={s} d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  layers: (s = 15) => <Svg size={s} d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />,
  play: (s = 15) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <title>Play</title>
      <path d="M5 3l14 9-14 9V3z" />
    </svg>
  ),
  plus: (s = 15) => <Svg size={s} d="M12 5v14M5 12h14" />,
  lock: (s = 15) => (
    <Svg
      size={s}
      d="M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 0110 0v4"
    />
  ),
  unlock: (s = 15) => (
    <Svg
      size={s}
      d="M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 019.9-1"
    />
  ),
  x: (s = 15) => <Svg size={s} d="M18 6L6 18M6 6l12 12" />,
  copy: (s = 15) => (
    <Svg
      size={s}
      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
    />
  ),
  externalLink: (s = 15) => (
    <Svg size={s} d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
  ),
  info: (s = 15) => <Svg size={s} d="M12 16v-4m0-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />,
  package: (s = 15) => (
    <Svg
      size={s}
      d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"
    />
  ),
  globe: (s = 15) => (
    <Svg
      size={s}
      d="M12 2a10 10 0 100 20A10 10 0 0012 2zM2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20"
    />
  ),
  chip: (s = 15) => (
    <Svg
      size={s}
      d="M9 3H5a2 2 0 00-2 2v4m6-6h6m-6 0v18m6-18h4a2 2 0 012 2v4m-6-6v18m0 0H9m6 0h4a2 2 0 002-2v-4M3 9v6m18-6v6M3 15h6m12 0h-6"
    />
  ),
  arrowLeft: (s = 15) => <Svg size={s} d="M19 12H5M12 5l-7 7 7 7" />,
  terminal: (s = 15) => <Svg size={s} d="M4 17l6-6-6-6M12 19h8" />,
  refresh: (s = 15) => (
    <Svg
      size={s}
      d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"
    />
  ),
  grid: (s = 15) => <Svg size={s} d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />,
  files: (s = 15) => (
    <Svg size={s} d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  ),
  settings: (s = 15) => (
    <Svg
      size={s}
      d="M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
    />
  ),
  menu: (s = 15) => <Svg size={s} d="M3 12h18M3 6h18M3 18h18" />,
};

// ── Design tokens ──────────────────────────────────────────────────────────────
const TOKENS = {
  color: {
    bg: "#f4f6f9",
    surface: "#ffffff",
    surfaceAlt: "#f0f3f7",
    border: "#dde3ec",
    borderMid: "#c4cdd9",
    text: "#0d1117",
    textMid: "#4a5568",
    textMuted: "#8896a5",
    accent: "#2563eb",
    accentBg: "#eef4ff",
    accentBorder: "#bfdbfe",
    nav: "#111827",
    navBg: "#0f172a",
    navText: "#94a3b8",
    navActive: "#e2e8f0",
  },
  font: {
    mono: "'JetBrains Mono', monospace",
    sans: "'Inter', system-ui, sans-serif",
  },
} as const;

const C = TOKENS.color;
const F = TOKENS.font;

// ── Page keys ─────────────────────────────────────────────────────────────────
// Single source of truth for page/navigation string literals.
// Using these constants instead of raw strings lets TypeScript catch typos
// and makes refactoring (renaming a page) a one-line change.

/** Top-level app pages (App component). */
const APP_PAGE = {
  LANDING: "landing",
  EXPLORER: "explorer",
  REVIEWER: "reviewer",
} as const;
type AppPage = (typeof APP_PAGE)[keyof typeof APP_PAGE];

/** Explorer-internal pages (Explorer component). */
const PAGE = {
  SOURCE: "source",
  METADATA: "metadata",
  OVERVIEW: "overview",
  SEAL: "seal",
  ARCHIVE: "archive",
  FILES: "files",
  // Service pages — keys match Service.key values
  EVALUATE: "evaluate",
  BUILD: "build",
  SBOM: "sbom",
  ACTIVATION: "activation",
  SWH: "swh",
} as const;
type ExplorerPage = (typeof PAGE)[keyof typeof PAGE];

/** Maps a Ree field key to the Explorer page where it can be edited. */
const FIELD_TO_PAGE: Record<string, ExplorerPage> = {
  origin_url: PAGE.SOURCE,
  source_type: PAGE.SOURCE,
  _sourceAvailable: PAGE.SOURCE,
  _sourceAcquiredBy: PAGE.SOURCE,
  runtime: PAGE.BUILD,
  build_runtime_script: PAGE.BUILD,
  activation_script: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.SWH,
  zenodo_doi: PAGE.ARCHIVE,
  dataverse_doi: PAGE.ARCHIVE,
};

// ── Shared stable styles ───────────────────────────────────────────────────────
// Styles that do NOT depend on props or state are defined here at module scope
// so they are created once, not on every render of every component.

/** Uppercase section label used throughout service pages and the overview. */
const S_SECTION_LABEL: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: 1.2,
  color: C.textMuted,
  fontFamily: F.sans,
  textTransform: "uppercase",
  fontWeight: 700,
};

/** Card-style surface panel (no overflow setting — callers spread extras in). */
const S_PANEL: React.CSSProperties = {
  background: C.surface,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
};

/** Small bold label used for panel column headers in the overview. */
const S_PANEL_HEADER_LABEL: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: C.text,
  letterSpacing: 0.3,
  fontFamily: F.sans,
};

// ── Level colors use a single-axis progress ramp (slate → indigo → blue → cyan → teal → emerald).
// This encodes only "how far along the scale" — not quality or urgency.
// Semantic red/amber/green are reserved for true status signals (errors, warnings, success).
const LEVELS: Level[] = [
  {
    n: 0,
    label: "None",
    color: "#94a3b8",
    bg: "#f1f5f9",
    ink: "#475569",
    short: "NONE",
    desc: "No reproducibility metadata at all.",
    problem: "No descriptions available.",
    fix: "Start by writing a README.",
  },
  {
    n: 1,
    label: "Natural Language",
    color: "#6366f1",
    bg: "#eef2ff",
    ink: "#3730a3",
    short: "NAT·LANG",
    desc: "Requirements described in a README only.",
    problem: "Likely imprecise and incomplete.",
    fix: "Create a formal dependency file (e.g. requirements.txt).",
  },
  {
    n: 2,
    label: "Manifest File",
    color: "#3b82f6",
    bg: "#eff6ff",
    ink: "#1d4ed8",
    short: "MANIFEST",
    desc: "A dependency manifest exists (e.g. requirements.txt).",
    problem: "Installs different versions on different days.",
    fix: "Pin required versions (e.g. pandas==2.1.0).",
  },
  {
    n: 3,
    label: "Top-level Pins",
    color: "#0ea5e9",
    bg: "#f0f9ff",
    ink: "#0369a1",
    short: "TOP·PINS",
    desc: "Top-level dependency versions are pinned.",
    problem: "Transitive dependencies still float.",
    fix: "Use a lockfile (e.g. poetry.lock).",
  },
  {
    n: 4,
    label: "Dependencies Locked",
    color: "#06b6d4",
    bg: "#ecfeff",
    ink: "#0e7490",
    short: "DEPS·LOCK",
    desc: "All dependencies fully locked via a lockfile.",
    problem: "No system deps (libblas, glibc, CUDA).",
    fix: "Add containers or VMs.",
  },
  {
    n: 5,
    label: "Container Env",
    color: "#14b8a6",
    bg: "#f0fdfa",
    ink: "#0f766e",
    short: "CONTAINER",
    desc: "A container image (e.g. Dockerfile) is provided.",
    problem: "Base image and apt-get are non-deterministic.",
    fix: "Use declarative specs (e.g. Nix).",
  },
  {
    n: 6,
    label: "Declarative System",
    color: "#10b981",
    bg: "#ecfdf5",
    ink: "#047857",
    short: "DECL·SYS",
    desc: "Full system environment declared declaratively (e.g. Nix).",
    problem: "Source code availability of packages.",
    fix: "Use long-term archives like Software Heritage.",
  },
  {
    n: 7,
    label: "Beyond",
    color: "#059669",
    bg: "#d1fae5",
    ink: "#065f46",
    short: "BEYOND",
    desc: "Long-term archive of packages, hardware env, and sources of non-determinism documented.",
    problem: null,
    fix: null,
  },
];

const EVALUATE_SVC: Service = {
  key: "evaluate",
  label: "Evaluate",
  IC: Ic.star,
  color: "#7c3aed",
  badge: { label: "Evaluated", color: "#7c3aed", bg: "#f5f3ff" },
  desc: "Scan the repository structure and score the reproducibility level based on available metadata.",
  requires: [{ field: "_sourceAvailable", label: "Source loaded in workspace" }],
  params: [
    {
      key: "strict",
      label: "Strict mode",
      type: "bool",
      default: false,
      hint: "Fail if any optional fields are missing",
    },
    {
      key: "swhid_check",
      label: "Check SWHID",
      type: "bool",
      default: true,
      hint: "Verify the SWHID is resolvable at Software Heritage",
    },
  ],
};

const SERVICES: Service[] = [
  {
    key: "build",
    label: "Build Runtime",
    IC: Ic.cpu,
    color: "#0891b2",
    badge: { label: "Built", color: "#0891b2", bg: "#ecfeff" },
    desc: "Execute the build_runtime_script to construct the runtime environment from scratch.",
    requires: [
      { field: "_sourceAvailable", label: "Source available" },
      { field: "build_runtime_script", label: "Build script" },
    ],
    params: [
      {
        key: "no_cache",
        label: "No cache",
        type: "bool",
        default: true,
        hint: "Pass --no-cache to docker build",
      },
      {
        key: "platform",
        label: "Platform",
        type: "select",
        default: "linux/amd64",
        options: ["linux/amd64", "linux/arm64", "linux/arm/v7"],
        hint: "Target build platform",
      },
    ],
  },
  {
    key: "sbom",
    label: "Generate SBOM",
    IC: Ic.package,
    color: "#16a34a",
    badge: { label: "SBOM ready", color: "#16a34a", bg: "#f0fdf4" },
    desc: "Run syft against the built runtime tarball to produce an SPDX 2.3 software bill of materials.",
    requires: [{ field: "runtime", label: "Runtime" }],
    params: [
      {
        key: "format",
        label: "Output format",
        type: "select",
        default: "spdx-json",
        options: ["spdx-json", "cyclonedx-json", "syft-json"],
        hint: "SBOM serialisation format",
      },
    ],
  },
  {
    key: "activation",
    label: "Test Activation",
    IC: Ic.shield,
    color: "#7c3aed",
    badge: { label: "Activation passed", color: "#7c3aed", bg: "#f5f3ff" },
    desc: "Load the runtime tarball and verify the environment activates correctly.",
    requires: [{ field: "activation_script", label: "Activation script" }],
    params: [
      {
        key: "timeout",
        label: "Timeout (s)",
        type: "text",
        default: "60",
        hint: "Max seconds to wait for container start",
      },
      {
        key: "verbose",
        label: "Verbose output",
        type: "bool",
        default: false,
        hint: "Print full stdout from container",
      },
    ],
  },
];

function defaultParamsForService(svc: Service): Record<string, unknown> {
  return Object.fromEntries((svc.params || []).map((p) => [p.key, p.default]));
}

function initialServiceParams(): ServiceParams {
  return Object.fromEntries(
    [EVALUATE_SVC, ...SERVICES].map((svc) => [svc.key, defaultParamsForService(svc)]),
  );
}

// ── Archival repositories ──────────────────────────────────────────────────────
interface ArchiveRepo {
  key: string;
  label: string;
  shortLabel: string;
  color: string;
  bg: string;
  border: string;
  url: string;
  desc: string;
  idLabel: string;
  idField: keyof Ree;
  idPlaceholder: string;
  params: ServiceParam[];
  requires: ServiceRequire[];
}

const ARCHIVE_REPOS: ArchiveRepo[] = [
  {
    key: "swh",
    label: "Software Heritage",
    shortLabel: "Sftw. Heritage",
    color: "#e4572e",
    bg: "#fff7f5",
    border: "#fbd0c4",
    url: "https://www.softwareheritage.org",
    desc: "Universal source code archive. Assigns a permanent SWHID intrinsic identifier tied to the exact content of your code.",
    idLabel: "SWHID",
    idField: "swhid",
    idPlaceholder: "swh:1:dir:…",
    params: [
      {
        key: "visit_type",
        label: "Visit type",
        type: "select",
        default: "git",
        options: ["git", "svn", "hg", "tar"],
        hint: "Repository type for the deposit",
      },
      {
        key: "metadata_only",
        label: "Metadata only",
        type: "bool",
        default: false,
        hint: "Only update metadata, skip re-archival if already present",
      },
    ],
    requires: [{ field: "_sourceAvailable", label: "Source available" }],
  },
  {
    key: "zenodo",
    label: "Zenodo",
    shortLabel: "Zenodo",
    color: "#1d6fa4",
    bg: "#f0f7ff",
    border: "#bfdbfe",
    url: "https://zenodo.org",
    desc: "CERN / OpenAIRE general-purpose research repository. Issues a citable DOI and supports versioning of datasets and software.",
    idLabel: "DOI",
    idField: "zenodo_doi",
    idPlaceholder: "10.5281/zenodo.xxxxxxx",
    params: [
      {
        key: "access",
        label: "Access",
        type: "select",
        default: "open",
        options: ["open", "embargoed", "restricted", "closed"],
        hint: "Access level for the deposit",
      },
      {
        key: "community",
        label: "Community",
        type: "text",
        default: "",
        hint: "Zenodo community slug to submit to (optional)",
      },
    ],
    requires: [
      { field: "name", label: "Name" },
      { field: "sbom", label: "SBOM" },
    ],
  },
  {
    key: "dataverse",
    label: "Dataverse",
    shortLabel: "Dataverse",
    color: "#5e4fa2",
    bg: "#f5f3ff",
    border: "#ddd6fe",
    url: "https://dataverse.org",
    desc: "Open-source research data repository platform. Widely used by universities and research institutions for FAIR data sharing.",
    idLabel: "Handle / DOI",
    idField: "dataverse_doi",
    idPlaceholder: "https://doi.org/10.7910/DVN/…",
    params: [
      {
        key: "server",
        label: "Server URL",
        type: "text",
        default: "https://dataverse.harvard.edu",
        hint: "Dataverse installation to deposit to",
      },
      {
        key: "dataverse",
        label: "Dataverse",
        type: "text",
        default: "root",
        hint: "Target dataverse collection",
      },
    ],
    requires: [{ field: "name", label: "Name" }],
  },
];

// ── Mock data ──────────────────────────────────────────────────────────────────
const MOCK_FILES: FileTreeNode[] = [
  {
    id: "1",
    name: "src",
    type: "folder",
    children: [
      {
        id: "11",
        name: "main.py",
        type: "file",
        content: `#!/usr/bin/env python3\n\ndef main():\n    print("REE v1.0")\n\nif __name__ == "__main__":\n    main()`,
      },
      {
        id: "12",
        name: "pipeline.py",
        type: "file",
        content: `class Pipeline:\n    def __init__(self, config):\n        self.config = config\n        self.steps = []\n\n    def run(self):\n        for step in self.steps:\n            step.execute()`,
      },
      {
        id: "13",
        name: "utils",
        type: "folder",
        children: [
          {
            id: "131",
            name: "hash.py",
            type: "file",
            content: `import hashlib\n\ndef sha256_file(path):\n    h = hashlib.sha256()\n    with open(path, "rb") as f:\n        for chunk in iter(lambda: f.read(8192), b""):\n            h.update(chunk)\n    return h.hexdigest()`,
          },
        ],
      },
    ],
  },
  {
    id: "2",
    name: "build_runtime.sh",
    type: "file",
    content: `#!/bin/bash\nset -euo pipefail\nDOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest .\ndocker save ree:latest | gzip > runtime.tar.gz\necho "Build complete."`,
  },
  {
    id: "3",
    name: "activation_test.sh",
    type: "file",
    content: `#!/bin/bash\nset -euo pipefail\n# Load the runtime tarball and verify the environment activates\ndocker load < runtime.tar.gz\ndocker run --rm --entrypoint="" ree:latest echo "ok"\necho "Activation test passed."`,
  },
  {
    id: "4",
    name: "sbom.spdx.json",
    type: "file",
    content: `{\n  "spdxVersion": "SPDX-2.3",\n  "dataLicense": "CC0-1.0",\n  "name": "ree-sbom"\n}`,
  },
  {
    id: "5",
    name: "Dockerfile",
    type: "file",
    content: `FROM python:3.11.7-slim-bookworm\nWORKDIR /app\nCOPY . .\nRUN pip install --no-cache-dir -r requirements.txt\nCMD ["python", "src/main.py"]`,
  },
  {
    id: "6",
    name: "README.md",
    type: "file",
    content: `# genomics-pipeline-v2\n\nA fully reproducible genomics pipeline environment.`,
  },
  {
    id: "7",
    name: "requirements.txt",
    type: "file",
    content: `numpy==1.26.4\npandas==2.2.1\nscipy==1.12.0\nbiopython==1.83\npysam==0.22.0\nclick>=8.0\ntqdm\nloguru==0.7.2\npytest==8.1.1\ncoverage`,
  },
  {
    id: "8",
    name: "pyproject.toml",
    type: "file",
    content: `[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n\n[project]\nname = "genomics-pipeline"\nversion = "2.0.0"\nrequires-python = ">=3.11"\ndependencies = [\n  "numpy>=1.26",\n  "pandas>=2.0",\n  "snakemake==8.4.6",\n  "pulp==2.8.0",\n]\n\n[project.optional-dependencies]\ndev = [\n  "pytest>=8.0",\n  "mypy",\n  "ruff",\n]`,
  },
  {
    id: "9",
    name: "environment.yml",
    type: "file",
    content: `name: genomics-pipeline\nchannels:\n  - conda-forge\n  - bioconda\n  - defaults\ndependencies:\n  - python=3.11.7\n  - samtools=1.19.2\n  - bwa=0.7.17\n  - gatk4=4.5.0.0\n  - bcftools=1.19\n  - htslib\n  - pip:\n    - pysam==0.22.0\n    - biopython==1.83`,
  },
  { id: "10", name: "runtime.tar.gz", type: "file", content: "(binary content)" },
];

function cloneTree(nodes: FileTreeNode[]): FileTreeNode[] {
  return (nodes || []).map((node) => ({
    ...node,
    children: node.children ? cloneTree(node.children) : undefined,
  }));
}

function makeWorkspaceFromOrigin(
  originUrl: string,
  sourceType: Ree["source_type"],
): FileTreeNode[] {
  const seed = cloneTree(MOCK_FILES);
  const repoName = (originUrl.split("/").filter(Boolean).pop() || "repo").replace(
    /\.(git|tar\.gz|tgz|zip)$/i,
    "",
  );

  if (sourceType === "tarball") {
    return [
      {
        id: `src-${Date.now()}`,
        name: repoName || "repo",
        type: "folder",
        tag: PAGE.SOURCE,
        children: [
          ...seed,
          {
            id: `src-meta-${Date.now()}`,
            name: "EXTRACTION_NOTE.txt",
            type: "file",
            tag: PAGE.SOURCE,
            content: `Extracted from tarball source: ${originUrl}`,
          },
        ],
      },
    ];
  }

  return [
    {
      id: `src-${Date.now()}`,
      name: repoName || "repo",
      type: "folder",
      tag: PAGE.SOURCE,
      children: seed,
    },
  ];
}

function makeWorkspaceFromArchiveUpload(archiveName: string): FileTreeNode[] {
  const root = archiveName.replace(/\.(tar\.gz|tgz|tar|zip)$/i, "") || "repo";
  return [
    {
      id: `up-${Date.now()}`,
      name: root,
      type: "folder",
      tag: PAGE.SOURCE,
      children: [
        ...cloneTree(MOCK_FILES),
        {
          id: `up-note-${Date.now()}`,
          name: "EXTRACTION_NOTE.txt",
          type: "file",
          tag: PAGE.SOURCE,
          content: `Extracted from uploaded archive: ${archiveName}`,
        },
      ],
    },
  ];
}

const DEMO_REE: Ree = {
  name: "genomics-pipeline-v2",
  swhid: "",
  origin_url: "https://github.com/lab/genomics-pipeline",
  source_type: "git",
  detected_dependencies: "",
  repro_level: "",
  runtime: "",
  build_runtime_script: "build_runtime.sh",
  sbom: "",
  activation_script: "activation_test.sh",
  hardware_description: {
    arch: "x86_64",
    memory: "16 GB",
    os: "Debian Bookworm",
    cpu: "Intel Xeon E5-2680",
  },
  _sourceAvailable: false,
  _sourceIncluded: true,
};

const SEALED_DEMO_REE: Ree = {
  ...DEMO_REE,
  swhid: "swh:1:dir:4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  runtime: "runtime.tar.gz",
  sbom: "sbom.spdx.json",
  zenodo_doi: "10.5281/zenodo.1234567",
  _evalLevel: 7,
  _sealedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), // 3 days ago
  _sealHash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  _sourceIncluded: true,
  _runtimeIncluded: true,
};

// ── Log generation ─────────────────────────────────────────────────────────────
function makeLogs(
  key: string,
  ree: Ree,
  params: Record<string, unknown>,
  newLevel: number,
): LogLine[] {
  const L = (type: LogLineType, msg: string): LogLine => ({ type, msg });
  const maps = {
    create: [
      L("info", "Validating REE fields..."),
      L("info", `  name:              ${ree.name || "(empty)"}`),
      L("info", `  origin_url:        ${ree.origin_url || "(empty)"}`),
      L("info", `  build_script:      ${ree.build_runtime_script || "(empty)"}`),
      L("info", `  sbom:              ${ree.sbom || "(empty)"}`),
      L("info", `  activation:        ${ree.activation_script || "(empty)"}`),
      L("info", "Registering REE object..."),
      L("ok", `REE id: ree-${Math.random().toString(16).slice(2, 10)}`),
      L("ok", "Manifest ready for download."),
    ],
    evaluate: [
      L("info", `Strict mode:      ${params.strict ? "yes" : "no"}`),
      L("info", `SWHID check:      ${params.swhid_check !== false ? "yes" : "no"}`),
      L("info", "Scanning repository structure..."),
      L("info", `  runtime:         ${ree.runtime || "not set"}`),
      L("info", `  sbom:            ${ree.sbom || "not set"}`),
      L("info", `  build_script:    ${ree.build_runtime_script || "not set"}`),
      L("info", `  activation:      ${ree.activation_script || "not set"}`),
      ree.swhid
        ? L("ok", `SWHID resolves: ${ree.swhid}`)
        : L("warn", "No SWHID — not yet archived"),
      L("info", "Computing score..."),
      L("ok", `Reproducibility level: L${newLevel} (${LEVELS[newLevel].label})`),
    ],
    build: [
      L("info", `Platform:  ${params.platform || "linux/amd64"}`),
      L("info", `No-cache:  ${params.no_cache !== false ? "yes" : "no"}`),
      L("info", `Reading ${ree.build_runtime_script || "build_runtime.sh"}...`),
      L("info", "Pulling base image: python:3.11.7-slim-bookworm"),
      L(
        "info",
        "$ DOCKER_BUILDKIT=1 docker build --no-cache --platform=" +
          (params.platform || "linux/amd64") +
          " -t ree:latest .",
      ),
      L("out", "Step 1/5 : FROM python:3.11.7-slim-bookworm"),
      L("out", "Step 2/5 : WORKDIR /app"),
      L("out", "Step 3/5 : COPY requirements.txt ."),
      L("out", "Step 4/5 : RUN pip install --no-cache-dir -r requirements.txt"),
      L("out", "Step 5/5 : COPY src/ ./src/"),
      L("info", "$ docker save ree:latest | gzip > runtime.tar.gz"),
      L(
        "ok",
        "Build complete. Output: " +
          (ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "runtime.tar.gz"),
      ),
      L("ok", "runtime.tar.gz written. Build successful."),
    ],
    sbom: [
      L("info", `Format:    ${params.format || "spdx-json"}`),
      L("info", `Target:    ${ree.runtime || "(not set)"}`),
      L(
        "info",
        "$ syft " +
          (ree.runtime || "runtime.tar.gz") +
          " -o " +
          (params.format || "spdx-json") +
          "=sbom.spdx.json",
      ),
      L("out", " ✔ Loaded image layers"),
      L("out", " ✔ Parsed image configuration"),
      L("out", " ✔ Catalogued contents"),
      L("out", "   ├── numpy 1.26.4"),
      L("out", "   ├── pandas 2.2.1"),
      L("out", "   ├── scipy 1.12.0"),
      L("out", "   ├── biopython 1.83"),
      L("out", "   └── ... 42 packages total"),
      L("info", "Writing sbom.spdx.json..."),
      L("ok", "SBOM generated: sbom.spdx.json"),
    ],
    activation: [
      L("info", `Timeout: ${params.timeout || "60"}s`),
      L("info", `Reading ${ree.activation_script || "activation_test.sh"}...`),
      L("info", `$ docker load < ${ree.runtime || "runtime.tar.gz"}`),
      L("out", "Loaded image: ree:latest"),
      L("info", '$ docker run --rm --entrypoint="" ree:latest echo ok'),
      L("out", "ok"),
      L("ok", "Container started and exited cleanly. Activation test passed."),
    ],
    swh: [
      L("info", `Visit type:     ${params.visit_type || "git"}`),
      L("info", `Metadata only:  ${params.metadata_only ? "yes" : "no"}`),
      L("info", "Preparing immutable source snapshot archive..."),
      L("info", `Snapshot: ${ree._sourceSnapshotArchive || "source-original.tar.gz"}`),
      L("info", "Connecting to Software Heritage API..."),
      L("info", `Depositing: ${ree.origin_url || ree.name}`),
      L("info", "Waiting for ingestion confirmation..."),
      L("info", "Computing SWHID from tree hash..."),
      L("ok", "Deposit accepted."),
      L("ok", `SWHID: swh:1:dir:${Math.random().toString(16).slice(2, 14)}`),
    ],
    zenodo: [
      L("info", `Access level:   ${params.access || "open"}`),
      L("info", `Community:      ${params.community || "(none)"}`),
      L("info", "Creating deposition on Zenodo..."),
      L("info", `Uploading SBOM: ${ree.sbom || "sbom.spdx.json"}`),
      L("info", `Uploading manifest: ${ree.name || "ree"}.manifest.json`),
      L("info", "Setting metadata (title, creators, description)..."),
      L("info", "Publishing deposition..."),
      L("ok", "Deposition published."),
      L("ok", `DOI: 10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`),
    ],
    dataverse: [
      L("info", `Server:     ${params.server || "https://dataverse.harvard.edu"}`),
      L("info", `Dataverse:  ${params.dataverse || "root"}`),
      L("info", "Creating dataset..."),
      L("info", "Uploading files..."),
      L("info", "Setting metadata fields..."),
      L("info", "Publishing dataset..."),
      L("ok", "Dataset published."),
      L("ok", `Handle: hdl:1902.1/${Math.floor(Math.random() * 90000 + 10000)}`),
    ],
  };
  return maps[key] || [L("ok", "Done.")];
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function allFilePaths(nodes: FileTreeNode[], prefix = ""): string[] {
  let paths = [];
  for (const n of nodes) {
    const p = prefix ? `${prefix}/${n.name}` : n.name;
    if (n.type === "file") paths.push(p);
    if (n.children) paths = paths.concat(allFilePaths(n.children, p));
  }
  return paths;
}

// Walk the file tree and return the node matching a given path string, or null.
function findFileByPath(nodes: FileTreeNode[], pathStr: string): FileTreeNode | null {
  const parts = pathStr.replace(/^\//, "").split("/").filter(Boolean);
  if (!parts.length) return null;
  let cursor = nodes;
  for (let i = 0; i < parts.length; i++) {
    const node = cursor?.find((n) => n.name === parts[i]);
    if (!node) return null;
    if (i === parts.length - 1) return node.type === "file" ? node : null;
    cursor = node.children;
  }
  return null;
}

// Detect a rough file type from the path, used for syntax-hinting the preview.
function fileType(path: string): string {
  if (!path) return "text";
  const ext = path.split(".").pop().toLowerCase();
  if (["sh", "bash"].includes(ext)) return "shell";
  if (
    ["dockerfile", "containerfile"].includes(path.split("/").pop().toLowerCase()) ||
    ext === "dockerfile"
  )
    return "dockerfile";
  if (["json", "jsonc"].includes(ext)) return "json";
  if (["py"].includes(ext)) return "python";
  if (["nix"].includes(ext)) return "nix";
  if (["md"].includes(ext)) return "markdown";
  if (["lock", "toml", "yaml", "yml"].includes(ext)) return "config";
  return "text";
}

// ── CSS ────────────────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  @keyframes spin    { to { transform: rotate(360deg); } }
  @keyframes fadeUp  { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  @keyframes slideIn { from { opacity:0; transform:translateX(10px); } to { opacity:1; transform:translateX(0); } }
  @keyframes pulseGlow { 0%,100% { box-shadow: 0 0 0 0 currentColor; } 50% { box-shadow: 0 0 0 4px transparent; } }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family: Inter, system-ui, sans-serif; background: #f4f6f9; }
  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#c4cdd9; border-radius:99px; }
  ::-webkit-scrollbar-thumb:hover { background:#8896a5; }
  input, select, button, textarea { font-family:inherit; outline:none; }
  input:focus, select:focus { border-color:#2563eb !important; box-shadow:0 0 0 3px #2563eb18 !important; }
  .nav-item { transition: background 0.12s, color 0.12s; }
`;

// ── Shared components ──────────────────────────────────────────────────────────
interface ToastProps {
  message: string;
  type: "success" | "error" | "info";
  onClose: () => void;
}
function Toast({ message, type, onClose }: ToastProps) {
  const palette = {
    success: ["#16a34a", "#f0fdf4"],
    error: ["#dc2626", "#fef2f2"],
    info: [C.accent, C.accentBg],
  };
  const [c, bg] = palette[type] || palette.info;
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        zIndex: 2000,
        background: bg,
        border: `1px solid ${c}30`,
        borderLeft: `3px solid ${c}`,
        borderRadius: 8,
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
        maxWidth: 340,
        animation: "slideIn 0.2s ease",
      }}
    >
      <span style={{ color: c, flexShrink: 0 }}>{Ic.info()}</span>
      <span style={{ fontSize: 14, color: C.text, fontFamily: F.sans, flex: 1 }}>{message}</span>
      <button
        type="button"
        onClick={onClose}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: C.textMuted,
          display: "flex",
        }}
      >
        {Ic.x()}
      </button>
    </div>
  );
}

// ── File tree ──────────────────────────────────────────────────────────────────
interface FileNodeProps {
  node: FileTreeNode;
  depth?: number;
  onSelect: (node: FileTreeNode) => void;
  selectedId: string | null;
  highlightedPaths?: Set<string>;
}
function FileNode({
  node,
  depth = 0,
  onSelect,
  selectedId,
  highlightedPaths = new Set(),
}: FileNodeProps) {
  const [open, setOpen] = useState(depth < 1);
  const isFolder = node.type === "folder";
  const isSel = selectedId === node.id;
  const isHighlighted = !isFolder && highlightedPaths.has(node.name);
  return (
    <div>
      <div
        onClick={() => (isFolder ? setOpen(!open) : onSelect(node))}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          padding: "4px 8px",
          paddingLeft: 8 + depth * 14,
          borderRadius: 5,
          cursor: "pointer",
          background: isSel ? C.accentBg : isHighlighted ? "#fef3c7" : "transparent",
          border: isHighlighted && !isSel ? "1px solid #fde68a" : "1px solid transparent",
          fontSize: 13,
          fontFamily: F.mono,
          transition: "background 0.1s",
          userSelect: "none",
          color: isSel ? C.accent : isHighlighted ? "#92400e" : isFolder ? C.text : C.textMid,
        }}
        onMouseEnter={(e) =>
          !isSel && (e.currentTarget.style.background = isHighlighted ? "#fef3c7" : C.surfaceAlt)
        }
        onMouseLeave={(e) =>
          !isSel && (e.currentTarget.style.background = isHighlighted ? "#fef3c7" : "transparent")
        }
      >
        {isFolder ? (
          <>
            <span style={{ color: C.textMuted, display: "flex", width: 12 }}>
              {open ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
            {Ic.folder(14)}
          </>
        ) : (
          <span style={{ marginLeft: 12, display: "flex" }}>{Ic.file(14)}</span>
        )}
        <span
          style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          {node.name}
        </span>
        {isHighlighted && !isSel && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              color: "#b45309",
              background: "#fef3c7",
              border: "1px solid #fde68a",
              borderRadius: 3,
              padding: "0 3px",
              fontFamily: F.sans,
              flexShrink: 0,
            }}
          >
            REF
          </span>
        )}
      </div>
      {isFolder &&
        open &&
        node.children?.map((c) => (
          <FileNode
            key={c.id}
            node={c}
            depth={depth + 1}
            onSelect={onSelect}
            selectedId={selectedId}
            highlightedPaths={highlightedPaths}
          />
        ))}
    </div>
  );
}

// ── SBOM contract helpers ──────────────────────────────────────────────────────
// ── ScriptPanel — script viewer + write panel with default templates ───────────
// scriptKind: "build" | "validate" | null (view-only)
// fieldKey: which ree field holds the script path
// files / onFilesChange: virtual repo file tree
// onReeChange: callback to update ree fields (e.g. set the script path)
interface ScriptTemplate {
  key: string;
  label: string;
  filename: string;
  content: string;
  suggestedOutput?: string;
}

function defaultScriptTemplates(
  scriptKind: "build" | "validate" | null,
  runtimeHint: string,
): ScriptTemplate[] {
  if (scriptKind === "validate") {
    const runtimeName =
      runtimeHint && runtimeHint !== "__skipped__" ? runtimeHint : "runtime.tar.gz";
    return [
      {
        key: "activation-smoke",
        label: "Activation smoke test",
        filename: "activation_test.sh",
        content: `#!/usr/bin/env bash
set -euo pipefail

RUNTIME_FILE="${runtimeName}"
IMAGE_TAG="ree:latest"

echo "[1/3] Loading runtime from $RUNTIME_FILE"
docker load < "$RUNTIME_FILE"

echo "[2/3] Running smoke check in $IMAGE_TAG"
docker run --rm --entrypoint "" "$IMAGE_TAG" sh -lc 'echo activation-ok'

echo "[3/3] Runtime activation test passed"
`,
      },
    ];
  }

  if (scriptKind !== "build") return [];

  return [
    {
      key: "docker-export",
      label: "Docker build + export tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/3] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/3] Exporting image to $OUTPUT_FILE"
docker save "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"

echo "[3/3] Done"
`,
    },
    {
      key: "docker-image-only",
      label: "Docker build (image ref output)",
      filename: "build_runtime.sh",
      suggestedOutput: "ree:latest",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"  # Keep this aligned with "Expected output" in the UI

echo "[1/2] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/2] Done"
echo "Built image: $IMAGE_TAG"
`,
    },
    {
      key: "nix-docker",
      label: "Nix build + Docker load + export",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/4] Building image artifact with Nix"
DRV_PATH="$(nix build .#dockerImage --print-out-paths --no-link)"

echo "[2/4] Loading image from Nix result"
docker load < "$DRV_PATH"

echo "[3/4] Tagging image as $IMAGE_TAG"
docker tag "$(docker images --format '{{.Repository}}:{{.Tag}}' | head -n 1)" "$IMAGE_TAG"

echo "[4/4] Exporting image to $OUTPUT_FILE"
docker save "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"
`,
    },
    {
      key: "conda-pack",
      label: "Conda env pack to tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI
ENV_NAME="ree"

echo "[1/3] Creating conda env from environment.yml"
conda env create -n "$ENV_NAME" -f environment.yml

echo "[2/3] Packing env"
conda run -n "$ENV_NAME" python -m pip install conda-pack
conda run -n "$ENV_NAME" conda-pack -o "$OUTPUT_FILE"

echo "[3/3] Done"
`,
    },
    {
      key: "venv-pip",
      label: "Python venv pack to tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/4] Creating virtual environment"
python -m venv .ree-venv
source .ree-venv/bin/activate

echo "[2/4] Installing dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[3/4] Packing environment"
tar -czf "$OUTPUT_FILE" .ree-venv

echo "[4/4] Done"
`,
    },
  ];
}

interface ScriptPanelProps {
  scriptKind: "build" | "validate" | null;
  fieldKey: keyof Ree;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  ree: Ree;
  onReeChange?: (ree: Ree) => void;
  onTemplateSuggestedOutput?: (output: string) => void;
  reviewerMode?: boolean;
  saveToWorkspaceOnly?: boolean;
}
function ScriptPanel({
  scriptKind,
  fieldKey,
  files,
  onFilesChange,
  ree,
  onReeChange,
  onTemplateSuggestedOutput,
  reviewerMode,
  saveToWorkspaceOnly = false,
}: ScriptPanelProps) {
  const scriptPath = (ree[fieldKey] as string) || "";
  const existingFile = scriptPath ? findFileByPath(files, scriptPath) : null;
  const hasScript = !!existingFile;

  // Detect origin type from origin_url
  const originUrl = ree.origin_url || "";
  const isGitHub = /github\.com/i.test(originUrl);
  const isGitLab = /gitlab\.com|gitlab\./i.test(originUrl);
  const isRemoteGit = (isGitHub || isGitLab) && !saveToWorkspaceOnly;

  // view | write
  type ScriptPanelMode = "view" | "write";
  const [mode, setMode] = useState<ScriptPanelMode>(
    hasScript ? "view" : scriptKind ? "write" : "view",
  );
  const [editorContent, setEditorContent] = useState(() => existingFile?.content || "");
  const [editorFilename, setEditorFilename] = useState(
    scriptPath || (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh"),
  );
  const [collapsed, setCollapsed] = useState(false);
  const runtimeHint = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const templates = useMemo(
    () => defaultScriptTemplates(scriptKind, runtimeHint),
    [scriptKind, runtimeHint],
  );
  const [templateKey, setTemplateKey] = useState(() => templates[0]?.key || "");

  useEffect(() => {
    if (!templates.length) {
      setTemplateKey("");
      return;
    }
    if (!templates.some((t) => t.key === templateKey)) setTemplateKey(templates[0].key);
  }, [templates, templateKey]);

  const handleModeChange = (m: "view" | "write") => {
    if (m === "write") {
      const f = scriptPath ? findFileByPath(files, scriptPath) : null;
      setEditorContent(f?.content || editorContent);
      setEditorFilename(scriptPath || editorFilename);
    }
    setMode(m);
    setCollapsed(false);
  };

  const commitFile = (fname: string, content: string) => {
    const newFile: FileTreeNode = {
      id: `vf-${fname}`,
      name: fname,
      type: "file",
      tag: PAGE.SOURCE,
      content,
    };
    const updated = [...files.filter((f) => f.name !== fname), newFile];
    onFilesChange?.(updated);
    onReeChange?.({ ...ree, [fieldKey]: fname });
  };

  const handleSave = () => {
    const fname =
      editorFilename.trim() ||
      (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh");
    commitFile(fname, editorContent);
    setMode("view");
  };

  const handleUseTemplate = () => {
    const selected = templates.find((t) => t.key === templateKey);
    if (!selected) return;
    setEditorFilename(scriptPath || selected.filename);
    setEditorContent(selected.content);
    if (scriptKind === "build" && selected.suggestedOutput) {
      onTemplateSuggestedOutput?.(selected.suggestedOutput);
    }
  };

  const ftype = fileType(scriptPath || editorFilename);
  const typeStyle = FILE_TYPE_COLORS[ftype] || FILE_TYPE_COLORS.text;
  const viewLines = existingFile ? (existingFile.content || "").split("\n") : null;

  const TABS: Array<{ key: ScriptPanelMode; label: string; icon: (s?: number) => JSX.Element }> = [
    ...(hasScript ? [{ key: "view" as ScriptPanelMode, label: scriptPath, icon: Ic.file }] : []),
    ...(!reviewerMode && scriptKind
      ? [
          {
            key: "write" as ScriptPanelMode,
            label: hasScript ? "Edit" : "Write",
            icon: Ic.terminal,
          },
        ]
      : []),
  ];

  const tabAccent: Record<ScriptPanelMode, string> = { view: "#16a34a", write: "#7c3aed" };
  const tabBg: Record<ScriptPanelMode, string> = { view: "#f0fdf4", write: "#f5f3ff" };

  // PR button label & forge icon
  const prHost = isGitHub ? "GitHub" : isGitLab ? "GitLab" : null;
  const prColor = isGitHub ? "#24292f" : "#fc6d26";
  const prBg = isGitHub ? "#f6f8fa" : "#fff4ef";
  const prBorder = isGitHub ? "#d0d7de" : "#fdb58b";

  return (
    <div
      style={{
        border: `1.5px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        marginBottom: 20,
        background: C.surface,
      }}
    >
      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          borderBottom: collapsed && mode === "view" ? "none" : `1px solid ${C.border}`,
          background: C.surfaceAlt,
        }}
      >
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {TABS.map((t) => {
            const isActive = mode === t.key;
            const acc = tabAccent[t.key];
            return (
              <button
                type="button"
                key={t.key}
                onClick={() => handleModeChange(t.key)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 14px",
                  background: isActive ? tabBg[t.key] : "transparent",
                  border: "none",
                  borderRight: `1px solid ${C.border}`,
                  borderBottom: isActive ? `2px solid ${acc}` : "2px solid transparent",
                  cursor: "pointer",
                  transition: "background 0.13s",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = `${C.border}40`;
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{ display: "flex", color: isActive ? acc : C.textMuted }}>
                  {t.icon(12)}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: t.key === "view" ? F.mono : F.sans,
                    color: isActive ? acc : C.textMid,
                    whiteSpace: "nowrap",
                    fontWeight: isActive ? 600 : 400,
                  }}
                >
                  {t.label}
                </span>
                {t.key === "view" && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      fontFamily: F.mono,
                      letterSpacing: 0.6,
                      textTransform: "uppercase",
                      padding: "1px 4px",
                      borderRadius: 3,
                      background: typeStyle.bg,
                      color: typeStyle.color,
                      border: `1px solid ${typeStyle.border}`,
                      marginLeft: 2,
                    }}
                  >
                    {typeStyle.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {/* Right: collapse toggle (view mode only) */}
        {mode === "view" && (
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "8px 12px",
              color: C.textMuted,
              display: "flex",
              alignItems: "center",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = C.textMid)}
            onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
          >
            {collapsed ? Ic.chevD(13) : Ic.chevR(13)}
          </button>
        )}
      </div>

      {/* Panel body */}
      {!(collapsed && mode === "view") && (
        <>
          {/* VIEW: read-only light code display */}
          {mode === "view" && (
            <div style={{ background: C.surfaceAlt }}>
              {viewLines === null ? (
                <div
                  style={{
                    padding: "12px 16px",
                    fontSize: 12,
                    fontFamily: F.mono,
                    color: "#f97316",
                  }}
                >
                  File not found in repository tree — check the path in metadata fields.
                </div>
              ) : viewLines.length === 0 ? (
                <div
                  style={{
                    padding: "12px 16px",
                    fontSize: 12,
                    fontFamily: F.mono,
                    color: C.textMuted,
                    fontStyle: "italic",
                  }}
                >
                  (empty file)
                </div>
              ) : (
                <div style={{ padding: "8px 0 10px" }}>
                  {viewLines.map((line, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "baseline" }}>
                      <span
                        style={{
                          display: "inline-block",
                          minWidth: 40,
                          textAlign: "right",
                          paddingRight: 16,
                          paddingLeft: 12,
                          fontSize: 11,
                          fontFamily: F.mono,
                          color: C.borderMid,
                          userSelect: "none",
                          flexShrink: 0,
                        }}
                      >
                        {i + 1}
                      </span>
                      <span
                        style={{
                          fontSize: 12,
                          fontFamily: F.mono,
                          lineHeight: 1.75,
                          color: line.startsWith("#")
                            ? "#94a3b8"
                            : /^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)
                              ? "#0369a1"
                              : /^(set |echo |docker |pip |apt-get )/.test(line)
                                ? "#15803d"
                                : line.includes("=") &&
                                    !line.startsWith(" ") &&
                                    !line.includes("==")
                                  ? "#b45309"
                                  : C.text,
                          whiteSpace: "pre",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "block",
                          paddingRight: 16,
                        }}
                      >
                        {line || " "}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* WRITE: editor with default templates in toolbar */}
          {mode === "write" && (
            <div>
              {/* Toolbar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderBottom: `1px solid ${C.border}`,
                  background: C.surfaceAlt,
                }}
              >
                {/* Filename */}
                <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
                  {Ic.terminal(11)}
                </span>
                <input
                  value={editorFilename}
                  onChange={(e) => setEditorFilename(e.target.value)}
                  placeholder="filename.sh"
                  style={{
                    flex: 1,
                    border: "none",
                    background: "transparent",
                    fontSize: 12,
                    fontFamily: F.mono,
                    color: C.textMid,
                    outline: "none",
                    minWidth: 0,
                  }}
                />

                {/* Template selector */}
                {templates.length > 0 && (
                  <>
                    <select
                      value={templateKey}
                      onChange={(e) => setTemplateKey(e.target.value)}
                      style={{
                        border: `1.5px solid ${C.border}`,
                        borderRadius: 5,
                        padding: "4px 8px",
                        fontSize: 11,
                        fontFamily: F.sans,
                        color: C.textMid,
                        background: C.surface,
                      }}
                    >
                      {templates.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleUseTemplate}
                      title="Insert selected template into editor"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "4px 10px",
                        borderRadius: 5,
                        cursor: "pointer",
                        border: `1px solid ${C.border}`,
                        background: C.surface,
                        color: C.textMid,
                        fontSize: 11,
                        fontWeight: 600,
                        fontFamily: F.sans,
                        transition: "all 0.13s",
                        flexShrink: 0,
                        whiteSpace: "nowrap",
                      }}
                      onMouseEnter={(e) => {
                        if (e.currentTarget) e.currentTarget.style.background = C.surfaceAlt;
                      }}
                      onMouseLeave={(e) => {
                        if (e.currentTarget) e.currentTarget.style.background = C.surface;
                      }}
                    >
                      {Ic.plus(12)} Apply template
                    </button>
                  </>
                )}

                <div style={{ width: 1, height: 16, background: C.border, flexShrink: 0 }} />

                {/* Save action */}
                {
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!editorContent.trim()}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "4px 10px",
                      borderRadius: 5,
                      cursor: !editorContent.trim() ? "default" : "pointer",
                      border: `1px solid ${C.accentBorder}`,
                      background: C.accentBg,
                      fontSize: 11,
                      fontWeight: 600,
                      fontFamily: F.sans,
                      color: C.accent,
                      transition: "all 0.13s",
                      flexShrink: 0,
                      whiteSpace: "nowrap",
                      opacity: !editorContent.trim() ? 0.4 : 1,
                    }}
                    onMouseEnter={(e) => {
                      if (editorContent.trim()) e.currentTarget.style.background = "#dbeafe";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = C.accentBg;
                    }}
                  >
                    {Ic.check(11)} Save to workspace
                  </button>
                }
              </div>

              {/* Editor area */}
              <textarea
                value={editorContent}
                onChange={(e) => setEditorContent(e.target.value)}
                placeholder={"#!/bin/bash\nset -euo pipefail\n\n# Write your script here..."}
                spellCheck={false}
                style={{
                  width: "100%",
                  minHeight: 200,
                  padding: "10px 14px",
                  fontFamily: F.mono,
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: C.text,
                  background: C.surface,
                  border: "none",
                  resize: "vertical",
                  outline: "none",
                  tabSize: 2,
                  display: "block",
                }}
                onKeyDown={(e) => {
                  if (e.key === "Tab") {
                    e.preventDefault();
                    const target = e.currentTarget;
                    const s = target.selectionStart;
                    const en = target.selectionEnd;
                    setEditorContent(`${editorContent.slice(0, s)}  ${editorContent.slice(en)}`);
                    requestAnimationFrame(() => {
                      target.selectionStart = target.selectionEnd = s + 2;
                    });
                  }
                }}
              />

              {/* Status bar */}
              <div
                style={{
                  padding: "5px 12px",
                  background: C.surfaceAlt,
                  borderTop: `1px solid ${C.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMuted }}>
                  {editorContent.split("\n").length} lines · Tab = 2 spaces
                </span>
                {isRemoteGit && (
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.sans,
                      color: C.textMuted,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    {Ic.link(10)}
                    <span>{isGitHub ? "github.com" : "gitlab.com"} · changes go via PR</span>
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── File picker input ──────────────────────────────────────────────────────────
interface FileTypeStyle {
  color: string;
  bg: string;
  border: string;
  label: string;
}
const FILE_TYPE_COLORS: Record<string, FileTypeStyle> = {
  shell: { color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0", label: "sh" },
  dockerfile: { color: "#0891b2", bg: "#ecfeff", border: "#a5f3fc", label: "container" },
  json: { color: "#7c3aed", bg: "#f5f3ff", border: "#ddd6fe", label: "json" },
  python: { color: "#2563eb", bg: "#eff6ff", border: "#bfdbfe", label: "py" },
  nix: { color: "#e4572e", bg: "#fff7f5", border: "#fbd0c4", label: "nix" },
  markdown: { color: "#64748b", bg: "#f8fafc", border: "#e2e8f0", label: "md" },
  config: { color: "#b45309", bg: "#fffbeb", border: "#fde68a", label: "cfg" },
  text: { color: "#475569", bg: "#f8fafc", border: "#e2e8f0", label: "txt" },
};

const PREVIEW_LINES = 6; // how many lines of content to show in the peek

interface FilePickerProps {
  value: string;
  onChange: (value: string) => void;
  files: FileTreeNode[];
  placeholder?: string;
  disabled?: boolean;
  onFocus?: () => void;
  filterFn?: (path: string) => boolean;
}
function FilePicker({
  value,
  onChange,
  files,
  placeholder,
  disabled,
  onFocus,
  filterFn,
}: FilePickerProps) {
  const [open, setOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  // Internal draft: allows the user to type freely; only committed to parent when valid
  const [draft, setDraft] = useState(value || "");

  // Sync draft when parent value changes externally (e.g. cleared by another action)
  const prevValue = useRef(value);
  if (prevValue.current !== value) {
    const old = prevValue.current;
    prevValue.current = value;
    // Only reset draft if user isn't mid-edit on something different
    setDraft((d) => (d === old ? value || "" : d));
  }

  const allPaths = allFilePaths(files);
  const paths = filterFn ? allPaths.filter(filterFn) : allPaths;

  const trimmedDraft = draft.trim();
  const matchedFile = trimmedDraft ? findFileByPath(files, trimmedDraft) : null;
  const notFound = trimmedDraft.length > 0 && !matchedFile;
  // Format violation: either file exists with wrong format, or extension clearly wrong
  const wrongFormat = filterFn && trimmedDraft.length > 0 && !filterFn(trimmedDraft);
  const ftype = fileType(trimmedDraft);
  const typeStyle = FILE_TYPE_COLORS[ftype] || FILE_TYPE_COLORS.text;

  // Derive preview lines from the matched file's content
  const previewLines = matchedFile
    ? (matchedFile.content || "").split("\n").slice(0, PREVIEW_LINES)
    : [];
  const hasMore = matchedFile
    ? (matchedFile.content || "").split("\n").length > PREVIEW_LINES
    : false;

  const isValid = matchedFile && !wrongFormat;

  // Border color reflects validation state
  const borderColor = notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.border;

  const handleDraftChange = (raw: string) => {
    setDraft(raw);
    setPreviewOpen(false);
    const trimmed = raw.trim();
    // Always allow clearing the field
    if (!trimmed) {
      onChange("");
      return;
    }
    const file = trimmed ? findFileByPath(files, trimmed) : null;
    const passesFormat = !filterFn || filterFn(trimmed);
    // Propagate valid value, or clear to empty if invalid
    onChange(file && passesFormat ? trimmed : "");
  };

  const handleSelect = (p: string) => {
    setDraft(p);
    setOpen(false);
    setPreviewOpen(true);
    // Dropdown only shows filtered paths, so always valid
    onChange(p);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Input row */}
      <div style={{ position: "relative" }}>
        <div
          style={{
            display: "flex",
            border: `1.5px solid ${borderColor}`,
            borderRadius: isValid && previewOpen ? "7px 7px 0 0" : "7px",
            background: disabled ? C.surfaceAlt : C.surface,
            overflow: "hidden",
            transition: "border-color 0.2s",
            boxShadow: isValid
              ? `0 0 0 3px #22c55e10`
              : notFound || wrongFormat
                ? `0 0 0 3px #f9731610`
                : "none",
          }}
        >
          {/* Status indicator left of input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 8px 0 10px",
              flexShrink: 0,
              color: notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.textMuted,
              transition: "color 0.2s",
            }}
          >
            {notFound || wrongFormat ? (
              <Svg
                size={14}
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            ) : isValid ? (
              Ic.check(14)
            ) : (
              Ic.file(14)
            )}
          </div>

          <input
            value={draft}
            onChange={(e) => handleDraftChange(e.target.value)}
            disabled={disabled}
            placeholder={placeholder || "path/to/file"}
            onFocus={onFocus}
            style={{
              flex: 1,
              border: "none",
              padding: "7px 4px 7px 0",
              fontSize: 14,
              fontFamily: F.mono,
              color: C.text,
              background: "transparent",
            }}
          />

          {/* Type badge — shown when file is matched */}
          {isValid && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "0 8px",
                borderLeft: `1px solid ${typeStyle.border}`,
                background: typeStyle.bg,
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.5,
                  color: typeStyle.color,
                  textTransform: "uppercase",
                }}
              >
                {typeStyle.label}
              </span>
            </div>
          )}

          {/* Peek toggle — shown when file is matched */}
          {isValid && !disabled && (
            <button
              type="button"
              onClick={() => setPreviewOpen((o) => !o)}
              title={previewOpen ? "Hide preview" : "Peek at file contents"}
              style={{
                background: previewOpen ? "#f0fdf4" : C.surfaceAlt,
                border: "none",
                borderLeft: `1px solid ${previewOpen ? "#bbf7d0" : C.border}`,
                padding: "7px 9px",
                cursor: "pointer",
                color: previewOpen ? "#16a34a" : C.textMid,
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                fontFamily: F.sans,
                fontWeight: 600,
                transition: "background 0.15s, color 0.15s",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                if (!previewOpen) {
                  e.currentTarget.style.background = C.accentBg;
                  e.currentTarget.style.color = C.accent;
                }
              }}
              onMouseLeave={(e) => {
                if (!previewOpen) {
                  e.currentTarget.style.background = C.surfaceAlt;
                  e.currentTarget.style.color = C.textMid;
                }
              }}
            >
              {Ic.terminal(13)}
              <span style={{ display: "none" }}>{previewOpen ? "hide" : "peek"}</span>
            </button>
          )}

          {/* Browse button */}
          {!disabled && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              title="Browse repository files"
              style={{
                background: open ? C.accentBg : C.surfaceAlt,
                border: "none",
                borderLeft: `1px solid ${C.border}`,
                padding: "7px 9px",
                cursor: "pointer",
                color: open ? C.accent : C.textMid,
                display: "flex",
                alignItems: "center",
                transition: "background 0.15s, color 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!open) {
                  e.currentTarget.style.background = C.accentBg;
                  e.currentTarget.style.color = C.accent;
                }
              }}
              onMouseLeave={(e) => {
                if (!open) {
                  e.currentTarget.style.background = C.surfaceAlt;
                  e.currentTarget.style.color = C.textMid;
                }
              }}
            >
              {Ic.folder()}
            </button>
          )}
        </div>

        {/* Browse dropdown */}
        {open && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              zIndex: 50,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
              maxHeight: 180,
              overflowY: "auto",
            }}
          >
            {paths.length === 0 ? (
              <div
                style={{
                  padding: "12px",
                  fontSize: 13,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  textAlign: "center",
                }}
              >
                {filterFn ? "No matching files in repository" : "No files in repository"}
              </div>
            ) : (
              paths.map((p) => (
                <div
                  key={p}
                  onClick={() => handleSelect(p)}
                  style={{
                    padding: "7px 12px",
                    fontSize: 13,
                    fontFamily: F.mono,
                    cursor: "pointer",
                    background: draft === p ? C.accentBg : "transparent",
                    color: draft === p ? C.accent : C.textMid,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                  onMouseEnter={(e) =>
                    draft !== p && (e.currentTarget.style.background = C.surfaceAlt)
                  }
                  onMouseLeave={(e) =>
                    draft !== p && (e.currentTarget.style.background = "transparent")
                  }
                >
                  <span style={{ display: "flex", opacity: 0.5 }}>{Ic.file(12)}</span>
                  {p}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Not-found / wrong-format warning strip */}
      {(notFound || wrongFormat) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 10px",
            background: "#fff7ed",
            border: `1px solid #fed7aa`,
            borderTop: "none",
            borderRadius: "0 0 6px 6px",
            animation: "fadeUp 0.15s ease",
          }}
        >
          <span style={{ fontSize: 11, color: "#c2410c", fontFamily: F.sans }}>
            {wrongFormat && notFound
              ? `Wrong format — expected ${placeholder || "the required format"}. File not found either.`
              : wrongFormat
                ? `Wrong format — this field only accepts ${placeholder || "the required format"}. Field not saved.`
                : "File not found in repository — field not saved until the path resolves."}
          </span>
        </div>
      )}

      {/* Inline file preview panel */}
      {isValid && previewOpen && (
        <div
          style={{
            border: `1.5px solid #22c55e`,
            borderTop: "none",
            borderRadius: "0 0 7px 7px",
            background: C.surfaceAlt,
            overflow: "hidden",
            animation: "fadeUp 0.15s ease",
          }}
        >
          {/* Preview header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "5px 12px",
              borderBottom: `1px solid ${C.border}`,
              background: C.surface,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ display: "flex", color: "#16a34a", opacity: 0.9 }}>{Ic.file(12)}</span>
              <span
                style={{ fontSize: 11, fontFamily: F.mono, color: C.textMid, letterSpacing: 0.3 }}
              >
                {trimmedDraft}
              </span>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.8,
                  textTransform: "uppercase",
                  padding: "1px 5px",
                  borderRadius: 3,
                  background: typeStyle.bg,
                  color: typeStyle.color,
                  border: `1px solid ${typeStyle.border}`,
                }}
              >
                {typeStyle.label}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setPreviewOpen(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: "2px",
                borderRadius: 3,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = C.textMid)}
              onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
            >
              {Ic.x(12)}
            </button>
          </div>

          {/* Code lines */}
          <div style={{ padding: "8px 0 6px" }}>
            {previewLines.map((line, i) => (
              <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 0 }}>
                <span
                  style={{
                    display: "inline-block",
                    minWidth: 36,
                    textAlign: "right",
                    paddingRight: 14,
                    paddingLeft: 12,
                    fontSize: 11,
                    fontFamily: F.mono,
                    color: C.borderMid,
                    userSelect: "none",
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.mono,
                    lineHeight: 1.7,
                    color: line.startsWith("#")
                      ? "#94a3b8"
                      : line.startsWith("FROM") ||
                          line.startsWith("RUN") ||
                          line.startsWith("COPY") ||
                          line.startsWith("CMD") ||
                          line.startsWith("WORKDIR")
                        ? "#0369a1"
                        : line.startsWith("set ") ||
                            line.startsWith("echo ") ||
                            line.startsWith("docker ")
                          ? "#15803d"
                          : line.includes("=") && !line.includes("==")
                            ? "#b45309"
                            : C.text,
                    whiteSpace: "pre",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    display: "block",
                    paddingRight: 14,
                  }}
                >
                  {line || " "}
                </span>
              </div>
            ))}
            {hasMore && (
              <div
                style={{
                  padding: "4px 12px 2px 36px",
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.textMuted,
                  fontStyle: "italic",
                }}
              >
                … {(matchedFile.content || "").split("\n").length - PREVIEW_LINES} more lines
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Form helpers ───────────────────────────────────────────────────────────────
const inp = (locked, extra = {}) => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

// ── Log view ───────────────────────────────────────────────────────────────────
interface LogStyleEntry {
  pre: string;
  color: string;
  bg: string;
}
const LOG_STYLE: Record<LogLineType, LogStyleEntry> = {
  info: { pre: "  INFO", color: "#475569", bg: "transparent" },
  ok: { pre: "    OK", color: "#16a34a", bg: "#f0fdf4" },
  warn: { pre: "  WARN", color: "#d97706", bg: "#fef3c7" },
  err: { pre: "   ERR", color: "#dc2626", bg: "#fef2f2" },
  out: { pre: "      ", color: "#1e293b", bg: "transparent" },
};

interface LogPanelProps {
  log: LogEntry | null;
  running?: boolean;
}
function LogPanel({ log }: LogPanelProps) {
  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        background: "#f8fafc",
        borderRadius: 10,
        border: `1px solid ${C.border}`,
        minHeight: 200,
      }}
    >
      {!log ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            minHeight: 200,
            gap: 8,
            color: C.textMuted,
          }}
        >
          {Ic.terminal()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>No output yet</span>
        </div>
      ) : (
        <div style={{ padding: "12px 0" }}>
          <div
            style={{
              padding: "6px 18px 12px",
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              borderBottom: `1px solid ${C.border}`,
              marginBottom: 4,
            }}
          >
            Last run:{" "}
            {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
          </div>
          {log.lines.map((line, i) => {
            const s = LOG_STYLE[line.type] || LOG_STYLE.info;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  padding: "3px 18px",
                  background: s.bg,
                  fontFamily: F.mono,
                  fontSize: 13,
                  lineHeight: 1.75,
                }}
              >
                <span
                  style={{
                    color: s.color,
                    fontWeight: 600,
                    marginRight: 14,
                    flexShrink: 0,
                    fontSize: 11,
                    opacity: 0.75,
                    minWidth: 52,
                  }}
                >
                  [{s.pre}]
                </span>
                <span style={{ color: s.color }}>{line.msg}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Field metadata ─────────────────────────────────────────────────────────────
interface FieldMeta {
  label: string;
  desc: string;
  example?: string;
  format?: string;
  howTo?: string;
  tools?: Array<{ label: string; url: string }>;
  toolCommands?: Array<{ label: string; cmd: string }>;
}
const FIELD_META: Record<string, FieldMeta> = {
  name: {
    label: "Name",
    desc: "A human-readable identifier for this REE.",
    example: "climate-model-v2.1.0",
    format: "Lowercase, hyphens allowed. Include a version suffix.",
    howTo:
      "Choose a name that reflects the project and version. This will appear in manifests and citations.",
    tools: [],
  },
  swhid: {
    label: "SWHID",
    desc: "Permanent Software Heritage identifier. Auto-assigned when you run Archive.",
    example: "swh:1:dir:4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    format: "swh:1:<type>:<sha1hex> — assigned by Software Heritage on deposit.",
    howTo:
      "You don't fill this manually. Run the Archive service and it will be assigned automatically.",
    tools: [],
  },
  origin_url: {
    label: "Origin URL",
    desc: "URL of the remote software origin or tarball download (optional if you upload locally).",
    example: "https://github.com/org/climate-model",
    format: "Use the clone/checkout URL provided by the host, or a direct tarball URL.",
    howTo:
      "To avoid archiving errors, use the provider clone URL and verify it works before submission (for example, `git clone <origin_url>` for git origins).",
    tools: [
      { label: "GitHub", url: "https://github.com" },
      { label: "GitLab", url: "https://gitlab.com" },
    ],
  },
  _sourceAcquiredBy: {
    label: "Origin Provisioning Status",
    desc: "How source files were provided to the workspace.",
    example: "Uploaded archive",
    format: "Automatically set after source acquisition.",
    howTo: "Set automatically based on whether source came from origin download or local upload.",
    tools: [],
  },
  source_type: {
    label: "Origin Type",
    desc: "Type of software origin used for Save Code Now style archiving.",
    example: "git",
    format:
      "One of: git, hg, svn, cvs, bzr, tarball. Tarball formats include: .jar, .tar, .tar.bz2, .tar.gz, .tar.lz, .tar.xz, .tar.zst, .zip.",
    howTo:
      "Use the clone/checkout URL from the provider UI, and verify it works (for example, `git clone <origin_url>` for git) before requesting download.",
    tools: [],
  },
  _sourceAvailable: {
    label: "In Workspace",
    desc: "Whether the repository has been materialized into the local workspace.",
    example: "Yes — repository is available in workspace",
    format: "Set automatically after source download or tarball upload.",
    howTo:
      "Download from origin or upload a tarball to populate the workspace before Evaluate/Build.",
    tools: [],
  },
  detected_dependencies: {
    label: "Detected Dependencies",
    desc: "Summary generated by Evaluate from dependency manifests found in the workspace.",
    example: "24 dependencies across 3 manifest files",
    format: "Auto-generated by Evaluate after a successful run.",
    howTo:
      "Run Evaluate after loading source. The scanner inspects requirements.txt, pyproject.toml, environment.yml, and package.json when present.",
    tools: [],
  },
  repro_level: {
    label: "Repro Level",
    desc: "Reproducibility level assigned by Evaluate.",
    example: "L4 · Dependencies Locked",
    format: "Auto-generated by Evaluate after a successful run.",
    howTo:
      "Run Evaluate to compute this value from available repository metadata and detected dependency/runtime signals.",
    tools: [],
  },
  runtime: {
    label: "Runtime",
    desc: "The built runtime — either a .tar.gz tarball (bundled in REE) or a container image ref (name or digest). Used as the syft scan target for SBOM generation.",
    example: "runtime.tar.gz  or  ree:latest",
    format:
      "A .tar.gz path (bundled) or a Docker/Podman image ref (not bundled). Set before running Build Runtime.",
    howTo: `Set this to whatever your build script produces. Two options:

Tarball (included in REE archive):
  docker save ree:latest | gzip > runtime.tar.gz
  → set runtime = "runtime.tar.gz"

Image ref (not bundled, rebuilt from script):
  docker build -t ree:latest .
  → set runtime = "ree:latest"

The SBOM step reads this field to know what to hand to syft.`,
    tools: [],
  },
  build_runtime_script: {
    label: "Build script",
    desc: "Script that builds the runtime from scratch. Used by the Build Runtime service.",
    example: "scripts/build_runtime.sh",
    format: "A shell script (.sh) relative to repo root. Must be executable.",
    howTo: `Create a script that builds your environment deterministically. The script should produce whatever is set as the runtime field. Example:

#!/bin/bash
set -euo pipefail
DOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest .
docker save ree:latest | gzip > runtime.tar.gz`,
    tools: [],
  },
  activation_script: {
    label: "Activation script",
    desc: "Script that loads the runtime tarball and verifies the container starts cleanly.",
    example: "scripts/activation_test.sh",
    format: "A shell script (.sh) relative to repo root. Should exit 0 if the container starts.",
    howTo: `Create a script that loads the runtime tarball and runs a minimal startup check. Example:

#!/bin/bash
set -euo pipefail
docker load < runtime.tar.gz
docker run --rm --entrypoint="" ree:latest echo ok`,
    tools: [],
  },
  sbom: {
    label: "SBOM",
    desc: "Software Bill of Materials — auto-generated by the Generate SBOM service from the runtime target.",
    example: "sbom.spdx.json",
    format: "SPDX 2.3 JSON. Generated automatically — assigned only after running Generate SBOM.",
    howTo:
      "Go to the Generate SBOM step and click Run after your runtime is ready. The SBOM file is produced and the sbom field is set automatically.",
    tools: [],
    toolCommands: [],
  },
};

// Which fields each service reads from REE (for cross-linking)
function svcReadableFields(svcKey: string): string[] {
  const map = {
    create: ["name", "origin_url"],
    evaluate: [
      "name",
      "origin_url",
      "source_type",
      "_sourceAvailable",
      "runtime",
      "build_runtime_script",
      "activation_script",
      "sbom",
      "swhid",
    ],
    build: ["_sourceAvailable", "runtime", "build_runtime_script"],
    sbom: ["runtime", "sbom"],
    activation: ["activation_script", "runtime"],
    archive: ["origin_url", "sbom", "swhid"],
  };
  return map[svcKey] || [];
}

function missingRequirements(svc: Service, ree: Ree): ServiceRequire[] {
  return (svc.requires || []).filter((r) => !ree[r.field]);
}

function tipTargetSectionStyle(active: boolean): React.CSSProperties {
  return {
    cursor: "pointer",
    background: active ? `${C.accentBg}75` : "transparent",
    borderLeftWidth: 3,
    borderLeftStyle: "solid",
    borderLeftColor: active ? C.accent : "transparent",
    boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
    transition: "background 0.15s, box-shadow 0.15s, border-color 0.15s",
  };
}

function tipTargetChip(active: boolean, idleLabel = "Click for tips"): React.ReactNode {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.sans,
        color: active ? C.accent : C.textMuted,
        background: active ? C.accentBg : C.surfaceAlt,
        border: `1px solid ${active ? C.accentBorder : C.border}`,
        borderRadius: 99,
        padding: "1px 7px",
        letterSpacing: 0.2,
      }}
    >
      {Ic.info(10)} {active ? "Tips open" : idleLabel}
    </span>
  );
}

// ── Field row with description ─────────────────────────────────────────────────
interface FieldRowProps {
  fieldKey: string;
  required?: boolean;
  children: React.ReactNode;
  locked?: boolean;
  usedBy?: Array<{ key: string; label: string; color: string }>;
  onFocus?: () => void;
  active?: boolean;
}
function FieldRow({
  fieldKey,
  required,
  children,
  locked,
  usedBy = [],
  onFocus,
  active,
}: FieldRowProps) {
  const meta = FIELD_META[fieldKey] || { label: fieldKey, desc: "" };
  const tipEnabled = !!onFocus;
  return (
    <div
      id={`field-${fieldKey}`}
      onFocus={onFocus}
      onClick={() => onFocus?.()}
      onMouseEnter={(e) => {
        if (!tipEnabled || active) return;
        e.currentTarget.style.background = `${C.accentBg}45`;
        e.currentTarget.style.borderLeftColor = C.accentBorder;
      }}
      onMouseLeave={(e) => {
        if (!tipEnabled || active) return;
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.borderLeftColor = "transparent";
      }}
      style={{
        display: "grid",
        gridTemplateColumns: "220px 1fr",
        gap: 20,
        alignItems: "start",
        borderBottom: `1px solid ${C.border}`,
        background: active ? `${C.accentBg}75` : "transparent",
        margin: "0 -20px",
        padding: "18px 20px",
        transition: "background 0.15s",
        cursor: tipEnabled ? "pointer" : "default",
        borderLeftWidth: 3,
        borderLeftStyle: "solid",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginBottom: 3,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: active ? C.accent : C.text,
              fontFamily: F.sans,
            }}
          >
            {meta.label}
          </span>
          {tipEnabled && tipTargetChip(!!active)}
          {required && (
            <span
              style={{
                fontSize: 11,
                color: "#ef4444",
                fontWeight: 700,
                fontFamily: F.sans,
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 3,
                padding: "1px 4px",
              }}
            >
              required
            </span>
          )}
          {locked && fieldKey !== "swhid" && (
            <span
              style={{
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
                background: C.surfaceAlt,
                border: `1px solid ${C.border}`,
                borderRadius: 3,
                padding: "1px 4px",
              }}
            >
              locked
            </span>
          )}
        </div>
        <p style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5, margin: "0 0 5px" }}>
          {meta.desc}
        </p>
        {usedBy.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {usedBy.map((s) => (
              <span
                key={s.key}
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: s.color,
                  background: `${s.color}10`,
                  border: `1px solid ${s.color}30`,
                  borderRadius: 3,
                  padding: "1px 5px",
                }}
              >
                {s.label}
              </span>
            ))}
          </div>
        )}
      </div>
      <div style={{ paddingTop: 2 }}>{children}</div>
    </div>
  );
}

// ── Dashboard field section card ───────────────────────────────────────────────
interface FieldSectionProps {
  title: string;
  icon: React.ReactNode;
  subtitle?: string;
  children: React.ReactNode;
  filledCount: number;
  totalCount: number;
}
function FieldSection({
  title,
  icon,
  subtitle,
  children,
  filledCount,
  totalCount,
}: FieldSectionProps) {
  const allFilled = filledCount === totalCount && totalCount > 0;
  const someFilled = filledCount > 0;
  const pct = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${allFilled ? "#22c55e40" : C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        transition: "border-color 0.3s",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          padding: "11px 20px",
          borderBottom: `1px solid ${allFilled ? "#22c55e30" : C.border}`,
          background: allFilled ? "#f0fdf4" : "#fafbfd",
          display: "flex",
          alignItems: "center",
          gap: 8,
          transition: "background 0.3s",
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            width: 3,
            height: 16,
            borderRadius: 99,
            background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
            flexShrink: 0,
            transition: "background 0.3s",
          }}
        />
        <span style={{ color: allFilled ? "#16a34a" : C.textMuted, display: "flex" }}>{icon}</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: 1,
            color: allFilled ? "#15803d" : C.text,
            textTransform: "uppercase",
            fontFamily: F.sans,
          }}
        >
          {title}
        </span>
        {subtitle && (
          <span
            style={{
              fontSize: 12,
              color: C.textMuted,
              fontWeight: 400,
              textTransform: "none",
              letterSpacing: 0,
            }}
          >
            — {subtitle}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {totalCount > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 40,
                height: 3,
                borderRadius: 99,
                background: C.border,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
                  borderRadius: 99,
                  transition: "width 0.4s",
                }}
              />
            </div>
            <span
              style={{
                fontSize: 11,
                fontFamily: F.mono,
                color: allFilled ? "#16a34a" : someFilled ? "#92400e" : C.textMuted,
                fontWeight: 600,
              }}
            >
              {filledCount}/{totalCount}
            </span>
          </div>
        )}
      </div>
      <div style={{ padding: "0 20px" }}>{children}</div>
    </div>
  );
}

// ── Field tip card — shown in sidebar when a field is focused ──────────────────
interface FieldTipCardProps {
  fieldKey: string;
  onDismiss: () => void;
}
function FieldTipCard({ fieldKey, onDismiss }: FieldTipCardProps) {
  const meta = FIELD_META[fieldKey];
  if (!meta) return null;
  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 4, animation: "fadeUp 0.15s ease" }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.accent }} />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 1.1,
              color: C.accent,
              textTransform: "uppercase",
              fontFamily: F.sans,
            }}
          >
            Field guide
          </span>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: C.textMuted,
            display: "flex",
            padding: 2,
            borderRadius: 4,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = C.text)}
          onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
        >
          {Ic.x(13)}
        </button>
      </div>

      <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
        {meta.label}
      </div>
      <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, margin: "0 0 14px" }}>
        {meta.desc}
      </p>

      {/* Example value */}
      {meta.example && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.8,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 6,
            }}
          >
            Example
          </div>
          <div
            style={{
              background: C.surfaceAlt,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              padding: "9px 12px",
              fontFamily: F.mono,
              fontSize: 13,
              color: C.accent,
              wordBreak: "break-all",
            }}
          >
            {meta.example}
          </div>
        </div>
      )}

      {/* Format */}
      {meta.format && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.8,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 6,
            }}
          >
            Format
          </div>
          <p
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
              fontFamily: F.mono,
            }}
          >
            {meta.format}
          </p>
        </div>
      )}

      {/* How to */}
      {meta.howTo && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.8,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 6,
            }}
          >
            How to get this
          </div>
          <pre
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.65,
              margin: 0,
              whiteSpace: "pre-wrap",
              fontFamily: meta.howTo.includes("\n") ? F.mono : "inherit",
            }}
          >
            {meta.howTo}
          </pre>
        </div>
      )}

      {/* Tool commands */}
      {meta.toolCommands && meta.toolCommands.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.8,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 8,
            }}
          >
            Commands
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {meta.toolCommands.map((tc, i) => (
              <div key={i}>
                <div
                  style={{ fontSize: 11, color: C.textMuted, fontFamily: F.sans, marginBottom: 4 }}
                >
                  {tc.label}
                </div>
                <div
                  style={{
                    background: "#0f172a",
                    borderRadius: 6,
                    padding: "10px 12px",
                    fontFamily: F.mono,
                    fontSize: 13,
                    color: "#94d2bd",
                    wordBreak: "break-all",
                    lineHeight: 1.6,
                  }}
                >
                  {tc.cmd}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tools / links */}
      {meta.tools && meta.tools.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 0.8,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 8,
            }}
          >
            Tools
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {meta.tools.map((t, i) => (
              <a
                key={i}
                href={t.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 13,
                  fontFamily: F.sans,
                  color: C.accent,
                  background: C.accentBg,
                  border: `1px solid ${C.accentBorder}`,
                  borderRadius: 5,
                  padding: "4px 10px",
                  textDecoration: "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {Ic.link(11)} {t.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface FieldTipsSidebarProps {
  focusedField: string | null;
  onFocusField?: (field: string) => void;
  onClear: () => void;
  tipFields?: string[];
  emptyMessage?: string;
  generalTips?: string[];
  generalTitle?: string;
}
function FieldTipsSidebar({
  focusedField,
  onFocusField,
  onClear,
  tipFields,
  emptyMessage,
  generalTips = [],
  generalTitle = "Step Purpose",
}: FieldTipsSidebarProps) {
  const activeField =
    focusedField && (!tipFields || tipFields.includes(focusedField)) ? focusedField : null;
  const showFieldPicker = !!(tipFields && tipFields.length > 0 && onFocusField);
  const emptyText =
    emptyMessage ||
    "Click any field — here or in the status bar above — to see examples, format rules, and commands.";
  const workflowTipFields = (tipFields || []).filter((fieldKey) => !!FIELD_META[fieldKey]);

  return (
    <div
      style={{
        width: 296,
        borderLeft: `1px solid ${C.border}`,
        background: C.surface,
        overflowY: "auto",
        padding: 20,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {showFieldPicker && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 1.1,
              color: C.textMuted,
              textTransform: "uppercase",
              fontFamily: F.sans,
            }}
          >
            Tips
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {(tipFields || []).map((fieldKey) => {
              const isActive = activeField === fieldKey;
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField(fieldKey)}
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    fontWeight: 700,
                    letterSpacing: 0.2,
                    color: isActive ? C.accent : C.textMid,
                    background: isActive ? C.accentBg : C.surfaceAlt,
                    border: `1px solid ${isActive ? C.accentBorder : C.border}`,
                    borderRadius: 99,
                    padding: "3px 9px",
                    cursor: "pointer",
                  }}
                >
                  {FIELD_META[fieldKey]?.label || fieldKey}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {generalTips.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ color: C.textMid, display: "flex" }}>{Ic.info(13)}</span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: 0.8,
                color: C.textMid,
                textTransform: "uppercase",
                fontFamily: F.sans,
              }}
            >
              {generalTitle}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {generalTips.map((tip, i) => (
              <p key={i} style={{ margin: 0, fontSize: 12, color: C.textMid, lineHeight: 1.55 }}>
                {tip}
              </p>
            ))}
          </div>
        </div>
      )}

      {activeField ? (
        <FieldTipCard fieldKey={activeField} onDismiss={onClear} />
      ) : workflowTipFields.length > 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ color: C.accent, display: "flex" }}>{Ic.info(13)}</span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: 0.8,
                color: C.accent,
                textTransform: "uppercase",
                fontFamily: F.sans,
              }}
            >
              Workflow tips
            </span>
          </div>
          <p style={{ fontSize: 12, color: C.textMid, lineHeight: 1.55, margin: 0 }}>
            No field selected. Here are the key tips for this page/workflow:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {workflowTipFields.map((fieldKey) => {
              const meta = FIELD_META[fieldKey];
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField?.(fieldKey)}
                  style={{
                    textAlign: "left",
                    padding: "8px 10px",
                    borderRadius: 8,
                    border: `1px solid ${C.accentBorder}`,
                    background: C.surface,
                    cursor: onFocusField ? "pointer" : "default",
                    display: "flex",
                    flexDirection: "column",
                    gap: 3,
                  }}
                >
                  <span
                    style={{ fontSize: 12, fontWeight: 700, color: C.text, fontFamily: F.sans }}
                  >
                    {meta?.label || fieldKey}
                  </span>
                  <span style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.45 }}>
                    {meta?.desc || ""}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <span style={{ color: C.accent, flexShrink: 0, marginTop: 1 }}>{Ic.info(13)}</span>
          <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, margin: 0 }}>{emptyText}</p>
        </div>
      )}
    </div>
  );
}

// ── Source URL field with draft/commit pattern ─────────────────────────────────
interface SourceUrlFieldProps {
  locked: boolean;
  committedValue: string;
  onCommit: (value: string) => void;
  onFocus?: () => void;
}
function SourceUrlField({ locked, committedValue, onCommit, onFocus }: SourceUrlFieldProps) {
  const [draft, setDraft] = useState(committedValue || "");
  const [checkState, setCheckState] = useState<"idle" | "checking" | "reachable" | "unreachable">(
    "idle",
  );
  const [checkedFor, setCheckedFor] = useState<string>("");

  const prevCommitted = useRef<string | undefined>(committedValue);
  if (prevCommitted.current !== committedValue) {
    prevCommitted.current = committedValue;
    setDraft(committedValue || "");
    if ((committedValue || "") !== checkedFor) {
      setCheckState("idle");
      setCheckedFor("");
    }
  }

  const isDirty = draft.trim() !== (committedValue || "").trim();

  const handleCheckReachable = async () => {
    const candidate = draft.trim();
    if (!candidate) return;
    setCheckState("checking");
    setCheckedFor(candidate);
    await new Promise((r) => setTimeout(r, 700));
    const reachable = /^https?:\/\/[^\s]+$/i.test(candidate);
    setCheckState(reachable ? "reachable" : "unreachable");
    if (reachable) onCommit(candidate);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
        <div style={{ flex: 1, position: "relative" }}>
          <div
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: C.textMuted,
              pointerEvents: "none",
            }}
          >
            {Ic.link()}
          </div>
          <input
            disabled={locked}
            value={draft}
            onChange={(e) => {
              const next = e.target.value;
              setDraft(next);
              if (!next.trim()) {
                onCommit("");
              }
              if (checkedFor && next.trim() !== checkedFor) {
                setCheckState("idle");
                setCheckedFor("");
              }
            }}
            onFocus={onFocus}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim()) handleCheckReachable();
            }}
            placeholder="https://github.com/org/repo"
            style={{
              ...inp(locked),
              paddingLeft: 32,
              borderColor: isDirty ? "#f59e0b" : undefined,
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleCheckReachable}
          disabled={locked || !draft.trim() || checkState === "checking"}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "7px 13px",
            borderRadius: 7,
            cursor: locked || !draft.trim() || checkState === "checking" ? "default" : "pointer",
            border: `1.5px solid ${draft.trim() ? C.accentBorder : C.border}`,
            background: draft.trim() ? C.accentBg : C.surfaceAlt,
            color: draft.trim() ? C.accent : C.textMuted,
            fontSize: 13,
            fontWeight: 600,
            fontFamily: F.sans,
            flexShrink: 0,
            transition: "all 0.15s",
            whiteSpace: "nowrap",
            opacity: locked ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!locked && draft.trim() && checkState !== "checking")
              e.currentTarget.style.filter = "brightness(0.96)";
          }}
          onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
        >
          {checkState === "checking" ? Ic.loader(13) : Ic.link(13)} Check reachable
        </button>
      </div>
      {isDirty && draft.trim() && (
        <div
          style={{
            fontSize: 11,
            color: "#92400e",
            fontFamily: F.sans,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.info(10)} Setting a new source will reset all workflow results.
        </div>
      )}
      {committedValue && !isDirty && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            fontSize: 11,
            fontFamily: F.mono,
            color: "#16a34a",
          }}
        >
          {Ic.check(10)}
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {committedValue}
          </span>
        </div>
      )}
      {checkState === "reachable" && checkedFor === draft.trim() && (
        <div
          style={{
            fontSize: 11,
            color: "#15803d",
            fontFamily: F.sans,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.check(10)} URL reachable
        </div>
      )}
      {checkState === "unreachable" && checkedFor === draft.trim() && (
        <div
          style={{
            fontSize: 11,
            color: "#b45309",
            fontFamily: F.sans,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.info(10)} URL not reachable (or invalid format)
        </div>
      )}
    </div>
  );
}

// ── Source upload field with pending confirm ────────────────────────────────────
interface SourceUploadFieldProps {
  locked: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onCommit: (payload: SourceUploadCommit) => void;
  committedName?: string;
}
function SourceUploadField({
  locked,
  disabled = false,
  disabledReason,
  onCommit,
  committedName,
}: SourceUploadFieldProps) {
  const archiveRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<SourceUploadCommit | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const inputDisabled = locked || disabled;

  const handleArchive = (file: File) => {
    if (!file || inputDisabled) return;
    setDropError(null);
    setPending({ mode: "archive", archiveName: file.name });
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (inputDisabled) return;
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    if (files.length !== 1 || !/\.(zip|tar|tar\.gz|tgz)$/i.test(files[0].name)) {
      setDropError("Only a single tarball/archive upload is allowed for direct repo upload.");
      return;
    }
    handleArchive(files[0]);
  };

  const handleConfirm = () => {
    if (!pending) return;
    onCommit(pending);
    setPending(null);
  };

  const handleCancel = () => setPending(null);

  return (
    <div style={{ padding: "8px 0 14px" }}>
      <input
        ref={archiveRef}
        type="file"
        accept=".zip,.tar,.tar.gz,.tgz"
        style={{ display: "none" }}
        onChange={(e) => handleArchive(e.target.files?.[0] as File)}
      />

      {/* Committed archive */}
      {committedName && !pending && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            borderRadius: 8,
            background: "#f0fdf4",
            border: "1.5px solid #bbf7d0",
            marginBottom: 8,
          }}
        >
          <span style={{ color: "#16a34a", display: "flex" }}>{Ic.archive()}</span>
          <span
            style={{
              flex: 1,
              fontSize: 13,
              fontFamily: F.mono,
              color: "#15803d",
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedName}
          </span>
          {!locked && (
            <button
              type="button"
              onClick={() => archiveRef.current?.click()}
              disabled={inputDisabled}
              style={{
                background: "none",
                border: `1px solid ${C.border}`,
                borderRadius: 5,
                cursor: "pointer",
                color: C.textMuted,
                fontSize: 11,
                fontFamily: F.sans,
                padding: "2px 8px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = C.accent;
                e.currentTarget.style.color = C.accent;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = C.border;
                e.currentTarget.style.color = C.textMuted;
              }}
            >
              {Ic.upload(11)} Replace
            </button>
          )}
        </div>
      )}

      {/* Pending confirmation */}
      {pending && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 8 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              borderRadius: 8,
              background: "#fffbeb",
              border: "1.5px solid #f59e0b",
            }}
          >
            <span style={{ color: "#d97706", display: "flex" }}>{Ic.archive()}</span>
            <span
              style={{
                flex: 1,
                fontSize: 13,
                fontFamily: F.mono,
                color: "#92400e",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {pending.archiveName}
            </span>
            <button
              type="button"
              onClick={handleConfirm}
              style={{
                background: "#fffbeb",
                border: "1.5px solid #f59e0b",
                borderRadius: 6,
                cursor: "pointer",
                color: "#b45309",
                fontSize: 12,
                fontWeight: 700,
                fontFamily: F.sans,
                padding: "4px 10px",
                display: "flex",
                alignItems: "center",
                gap: 4,
                flexShrink: 0,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.96)")}
              onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
            >
              {Ic.check(11)} Add to workspace
            </button>
            <button
              type="button"
              onClick={handleCancel}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: 2,
                borderRadius: 4,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#dc2626")}
              onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
            >
              {Ic.x(13)}
            </button>
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#92400e",
              fontFamily: F.sans,
              display: "flex",
              alignItems: "center",
              gap: 4,
              paddingLeft: 2,
            }}
          >
            {Ic.info(10)} Setting a new source will reset all workflow results.
          </div>
        </div>
      )}

      {/* Drop zone — always show if no committed file yet, or for replacement */}
      {!committedName && !pending && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!inputDisabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !inputDisabled && archiveRef.current?.click()}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "22px 16px",
            borderRadius: 8,
            cursor: inputDisabled ? "default" : "pointer",
            border: `1.5px dashed ${dragging ? C.accent : C.borderMid}`,
            background: dragging ? C.accentBg : C.bg,
            transition: "all 0.15s",
            opacity: inputDisabled ? 0.55 : 1,
          }}
          onMouseEnter={(e) => {
            if (!inputDisabled) {
              e.currentTarget.style.borderColor = C.accent;
              e.currentTarget.style.background = C.accentBg;
            }
          }}
          onMouseLeave={(e) => {
            if (!dragging) {
              e.currentTarget.style.borderColor = C.borderMid;
              e.currentTarget.style.background = C.bg;
            }
          }}
        >
          <span style={{ color: dragging ? C.accent : C.textMuted, display: "flex" }}>
            {Ic.upload(18)}
          </span>
          <span
            style={{ fontSize: 13, color: dragging ? C.accent : C.textMid, fontFamily: F.sans }}
          >
            Drop archive or <span style={{ color: C.accent, fontWeight: 600 }}>browse archive</span>
          </span>
          <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, marginTop: 4 }}>
            .zip · .tar · .tar.gz
          </span>
        </div>
      )}

      {disabledReason && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: C.textMuted,
            fontFamily: F.sans,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.info(10)} {disabledReason}
        </div>
      )}

      {dropError && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: "#b45309",
            fontFamily: F.sans,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.info(10)} {dropError}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RuntimeField — runtime tar.gz field with include/skip toggle
// ══════════════════════════════════════════════════════════════════════════════
interface RuntimeFieldProps {
  locked: boolean;
  ree: Ree;
  onChange: (ree: Ree) => void;
  onFocus?: () => void;
  active?: boolean;
  usedBy?: Array<{ key: string; label: string; color: string }>;
  files: FileTreeNode[];
}
function RuntimeField({
  locked,
  ree,
  onChange,
  onFocus,
  active,
  usedBy,
  files,
}: RuntimeFieldProps) {
  const val = ree.runtime || "";
  const isSkipped = val === "__skipped__";
  const isTarball = !isSkipped && /\.(tar\.gz|tgz)$/i.test(val);
  const isImageRef = !isSkipped && !!val && !isTarball;
  const mode = isSkipped ? "skip" : isImageRef ? "image" : "tarball";

  const set = (k: string, v: unknown) => onChange({ ...ree, [k]: v });

  const handleModeChange = (m: "tarball" | "image" | "skip") => {
    if (locked) return;
    if (m === "tarball") set("runtime", "");
    if (m === "image") set("runtime", isImageRef ? val : "");
    if (m === "skip") set("runtime", "__skipped__");
  };

  const meta = FIELD_META["runtime"];

  return (
    <div
      id="field-runtime"
      onFocus={onFocus}
      onClick={() => onFocus?.()}
      onMouseEnter={(e) => {
        if (!onFocus || active) return;
        e.currentTarget.style.background = `${C.accentBg}45`;
        e.currentTarget.style.borderLeftColor = C.accentBorder;
      }}
      onMouseLeave={(e) => {
        if (!onFocus || active) return;
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.borderLeftColor = "transparent";
      }}
      style={{
        display: "grid",
        gridTemplateColumns: "220px 1fr",
        gap: 20,
        alignItems: "start",
        borderBottom: `1px solid ${C.border}`,
        background: active ? `${C.accentBg}75` : "transparent",
        margin: "0 -20px",
        padding: "18px 20px",
        transition: "background 0.15s",
        cursor: onFocus ? "pointer" : "default",
        borderLeftWidth: 3,
        borderLeftStyle: "solid",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      {/* Left: label + description + used-by */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginBottom: 3,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: active ? C.accent : C.text,
              fontFamily: F.sans,
            }}
          >
            {meta.label}
          </span>
          {!!onFocus && tipTargetChip(!!active)}
        </div>
        <p style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5, margin: "0 0 5px" }}>
          {meta.desc}
        </p>
        {usedBy && usedBy.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {usedBy.map((s) => (
              <span
                key={s.key}
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: s.color,
                  background: `${s.color}10`,
                  border: `1px solid ${s.color}30`,
                  borderRadius: 3,
                  padding: "1px 5px",
                }}
              >
                {s.label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Right: mode toggle + input */}
      <div style={{ paddingTop: 2, display: "flex", flexDirection: "column", gap: 10 }}>
        {/* mode toggle: Tarball | Image ref only */}
        <div style={{ display: "flex", gap: 5 }}>
          {(
            [
              { id: "tarball", label: "Tarball", icon: Ic.archive },
              { id: "image", label: "Image ref", icon: Ic.cpu },
            ] as const
          ).map((opt) => {
            const isActive = mode === opt.id || (mode === "skip" && opt.id === "tarball");
            return (
              <button
                type="button"
                key={opt.id}
                onClick={() => handleModeChange(opt.id)}
                disabled={locked}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 5,
                  padding: "6px 8px",
                  borderRadius: 7,
                  cursor: locked ? "default" : "pointer",
                  border: `1.5px solid ${isActive ? C.accent : C.border}`,
                  background: isActive ? C.accentBg : C.surface,
                  fontSize: 11,
                  fontWeight: 600,
                  color: isActive ? C.accent : C.textMid,
                  fontFamily: F.sans,
                  transition: "all 0.15s",
                  opacity: locked ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!locked && !isActive) e.currentTarget.style.borderColor = C.borderMid;
                }}
                onMouseLeave={(e) => {
                  if (!locked && !isActive) e.currentTarget.style.borderColor = C.border;
                }}
              >
                <span style={{ display: "flex" }}>{opt.icon(11)}</span>
                {opt.label}
              </button>
            );
          })}
        </div>

        {/* tarball mode: file picker */}
        {(mode === "tarball" || mode === "skip") && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <FilePicker
              disabled={locked}
              value={isTarball ? val : ""}
              onChange={(v) => set("runtime", v)}
              files={files}
              placeholder="runtime.tar.gz"
              onFocus={onFocus}
              filterFn={(p) => /\.(tar\.gz|tgz)$/i.test(p)}
            />
            <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.5 }}>
              Bundled into the REE archive on deposit. Produced by your build script via{" "}
              <code
                style={{
                  fontFamily: F.mono,
                  fontSize: 10.5,
                  background: C.surfaceAlt,
                  padding: "1px 4px",
                  borderRadius: 3,
                }}
              >
                docker save … | gzip
              </code>
              .
            </div>
            {isSkipped && (
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  padding: "8px 11px",
                  background: "#fff7ed",
                  border: "1px solid #fde68a",
                  borderRadius: 7,
                }}
              >
                <span style={{ color: "#d97706", display: "flex", flexShrink: 0, marginTop: 1 }}>
                  {Ic.info(12)}
                </span>
                <div style={{ fontSize: 11, color: "#92400e", lineHeight: 1.5 }}>
                  Tarball will <strong>not</strong> be bundled in the REE archive. Ensure it is
                  reproducible from the build script alone.
                </div>
              </div>
            )}
          </div>
        )}

        {/* image ref mode: free text */}
        {mode === "image" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input
              disabled={locked}
              value={isImageRef ? val : ""}
              onChange={(e) => set("runtime", e.target.value)}
              onFocus={onFocus}
              placeholder="ree:latest  or  sha256:abc123…"
              style={inp(locked)}
            />
            <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.5 }}>
              A Docker/Podman image name or digest. Not bundled in the REE — the image must be
              rebuilt from the build script. Used by the SBOM step as the syft scan target.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE: Source Repo Entry
// ══════════════════════════════════════════════════════════════════════════════
interface PageSourceRepoEntryProps {
  ree: Ree;
  onChange: (ree: Ree) => void;
  locked: boolean;
  repoMode: string;
  onRepoModeChange: (mode: string) => void;
  onSourceChange: () => void;
  badges: Badges;
  onDownloadSource: (originType: Ree["source_type"]) => void;
  onWorkspaceUpload: (payload: SourceUploadCommit) => void;
  onRemoveWorkspaceSource: () => void;
  downloadRunning: boolean;
  downloadDone: boolean;
  onGoService: (key: string) => void;
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}
function PageSourceRepoEntry({
  ree,
  onChange,
  locked,
  repoMode,
  onRepoModeChange,
  onSourceChange,
  badges,
  onDownloadSource,
  onWorkspaceUpload,
  onRemoveWorkspaceSource,
  downloadRunning,
  downloadDone,
  onGoService,
  focusedField,
  setFocusedField,
}: PageSourceRepoEntryProps) {
  const set = (k: string, v: unknown) => onChange({ ...ree, [k]: v });
  const focus = (key: string) => setFocusedField(key);
  const [originTypeDraft, setOriginTypeDraft] = useState<Ree["source_type"]>(ree.source_type || "");
  const sourceInWorkspace = !!ree._sourceAvailable;
  const sourceIncluded = sourceInWorkspace && !!ree._sourceIncluded;
  const toggleSourceIncluded = () => {
    if (locked || !sourceInWorkspace) return;
    onChange({ ...ree, _sourceIncluded: !sourceIncluded });
  };

  useEffect(() => {
    if (!sourceInWorkspace && ree._sourceIncluded) {
      onChange({ ...ree, _sourceIncluded: false });
    }
  }, [sourceInWorkspace, ree._sourceIncluded]);

  useEffect(() => {
    setOriginTypeDraft(ree.source_type || "");
  }, [ree.source_type]);

  useEffect(() => {
    if (focusedField) {
      const el = document.getElementById(`field-${focusedField}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [focusedField]);

  // For each field, which services use it
  const fieldUsedBy = (fieldKey: string): Service[] =>
    [EVALUATE_SVC, ...SERVICES].filter((s) => svcReadableFields(s.key).includes(fieldKey));

  const sourceFromUpload = ree._sourceAcquiredBy === "upload" && !!ree._sourceAvailable;
  const sourceFromDownload = ree._sourceAcquiredBy === "download" && !!ree._sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";
  const sourceFilled = [
    ree.origin_url,
    ree._sourceAcquiredBy,
    ree._sourceAvailable ? "yes" : "",
  ].filter(Boolean).length;
  const canDownload =
    !!ree.origin_url && !!originTypeDraft && repoMode === "url" && !sourceFromUpload;
  const canUpload = repoMode === "upload" && !sourceFromDownload;
  const [workspaceBrowseHover, setWorkspaceBrowseHover] = React.useState(false);
  const downloadLabel = downloadRunning
    ? "Downloading source..."
    : sourceFromUpload
      ? "Source uploaded"
      : sourceFromDownload
        ? "Source downloaded"
        : "Download source files locally";

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0, overflow: "hidden" }}>
      {/* Scrollable left — fields */}
      <div style={{ flex: 1, overflowY: "auto", padding: 28, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: 0.5,
                textTransform: "uppercase",
                fontFamily: F.sans,
                color: C.textMuted,
              }}
            >
              Fields
            </h2>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Source — first, everything depends on it */}
          <FieldSection
            title="Source Repository"
            icon={Ic.globe()}
            filledCount={sourceFilled}
            totalCount={3}
          >
            <FieldRow
              fieldKey="origin_url"
              locked={locked}
              usedBy={fieldUsedBy("origin_url")}
              onFocus={() => focus("origin_url")}
              active={focusedField === "origin_url"}
            >
              <SourceUrlField
                locked={locked}
                committedValue={ree.origin_url}
                onCommit={(v) => {
                  set("origin_url", v);
                }}
                onFocus={() => focus("origin_url")}
              />
            </FieldRow>

            <div style={{ padding: "12px 0 0" }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                {["url", "upload"].map((m) => (
                  <button
                    type="button"
                    key={m}
                    onClick={() => {
                      if (locked || m === repoMode) return;
                      onRepoModeChange(m);
                      if (m === "upload") setOriginTypeDraft("");
                    }}
                    style={{
                      flex: 1,
                      padding: "7px",
                      borderRadius: 7,
                      cursor: locked ? "default" : "pointer",
                      border: `1.5px solid ${repoMode === m ? C.accent : C.border}`,
                      background: repoMode === m ? C.accentBg : C.surface,
                      fontSize: 13,
                      fontWeight: 600,
                      color: repoMode === m ? C.accent : C.textMid,
                      fontFamily: F.sans,
                      transition: "all 0.15s",
                    }}
                  >
                    {m === "url" ? "⇢ Origin URL" : "⤒ Upload tarball"}
                  </button>
                ))}
              </div>
            </div>
            {repoMode === "upload" && (
              <SourceUploadField
                locked={locked}
                disabled={!canUpload}
                disabledReason={
                  sourceFromDownload
                    ? "Source is already populated via origin download. Change source to switch method."
                    : undefined
                }
                committedName={ree._uploadedArchive}
                onCommit={(payload) => {
                  onWorkspaceUpload(payload);
                }}
              />
            )}

            {repoMode === "url" && (
              <>
                <FieldRow
                  fieldKey="source_type"
                  required
                  locked={locked}
                  usedBy={fieldUsedBy("source_type")}
                  onFocus={() => focus("source_type")}
                  active={focusedField === "source_type"}
                >
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <select
                      disabled={locked}
                      value={originTypeDraft}
                      onChange={(e) => {
                        setOriginTypeDraft(e.target.value as Ree["source_type"]);
                      }}
                      onFocus={() => focus("source_type")}
                      style={{ ...inp(locked), flex: 1 }}
                    >
                      <option value="">Select origin type</option>
                      <option value="git">git</option>
                      <option value="hg">hg</option>
                      <option value="svn">svn</option>
                      <option value="cvs">cvs</option>
                      <option value="bzr">bzr</option>
                      <option value="tarball">tarball</option>
                    </select>

                    <div>
                      <button
                        type="button"
                        disabled={locked || !canDownload || downloadRunning}
                        onClick={() => onDownloadSource(originTypeDraft)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "8px 12px",
                          borderRadius: 7,
                          cursor: locked || !canDownload || downloadRunning ? "default" : "pointer",
                          border: `1.5px solid ${downloadDone ? "#22c55e" : C.accent}`,
                          background: downloadDone ? "#f0fdf4" : C.accentBg,
                          color: downloadDone ? "#15803d" : C.accent,
                          fontSize: 13,
                          fontWeight: 700,
                          fontFamily: F.sans,
                          width: "fit-content",
                          opacity: locked || !canDownload ? 0.6 : 1,
                        }}
                      >
                        {downloadRunning ? Ic.loader(13) : Ic.download(13)}
                        {downloadLabel}
                      </button>
                    </div>
                  </div>
                </FieldRow>
              </>
            )}

            <FieldRow
              fieldKey="_sourceAcquiredBy"
              required={false}
              locked={true}
              usedBy={[
                { key: "evaluate", label: "Evaluate", color: "#7c3aed" },
                { key: "build", label: "Build Runtime", color: "#0891b2" },
              ]}
            >
              <input
                disabled
                value={sourceProvisionStatus}
                style={{
                  ...inp(true, {
                    cursor: "not-allowed",
                    color: sourceInWorkspace ? C.text : C.textMuted,
                    fontWeight: 600,
                  }),
                }}
              />
            </FieldRow>

            <FieldRow
              fieldKey="_sourceAvailable"
              required={false}
              locked={true}
              usedBy={[
                { key: "evaluate", label: "Evaluate", color: "#7c3aed" },
                { key: "build", label: "Build Runtime", color: "#0891b2" },
              ]}
              onFocus={() => focus("_sourceAvailable")}
              active={focusedField === "_sourceAvailable"}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <button
                    type="button"
                    onClick={() => onGoService(PAGE.FILES)}
                    style={{
                      ...inp(false, {
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 8,
                        cursor: "pointer",
                      }),
                      background: workspaceBrowseHover ? C.accentBg : C.surface,
                      borderColor: workspaceBrowseHover ? C.accentBorder : C.border,
                      flex: 1,
                    }}
                    title="Browse files"
                    onMouseEnter={() => setWorkspaceBrowseHover(true)}
                    onMouseLeave={() => setWorkspaceBrowseHover(false)}
                  >
                    <span
                      style={{
                        color: sourceInWorkspace ? "#15803d" : C.textMuted,
                        fontWeight: 600,
                        fontFamily: F.sans,
                      }}
                    >
                      {sourceInWorkspace
                        ? "Yes — repository is available in workspace"
                        : "No — source not in workspace yet"}
                    </span>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        color: C.accent,
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: F.sans,
                        flexShrink: 0,
                      }}
                    >
                      {Ic.files(12)} Browse files
                    </span>
                  </button>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginLeft: 2,
                      flexShrink: 0,
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                      <div
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: 0.7,
                          textTransform: "uppercase",
                          color: sourceIncluded ? C.textMid : C.textMuted,
                          fontFamily: F.sans,
                        }}
                      >
                        Included
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: sourceIncluded ? "#b45309" : C.textMuted,
                          fontFamily: F.sans,
                        }}
                      >
                        {sourceIncluded ? "Yes" : "No"}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={toggleSourceIncluded}
                      aria-pressed={sourceIncluded}
                      disabled={locked || !sourceInWorkspace}
                      title={
                        !sourceInWorkspace
                          ? "Source must be in workspace before it can be included"
                          : sourceIncluded
                            ? "Source will be included in final REE"
                            : "Source will be excluded from final REE"
                      }
                      style={{
                        width: 36,
                        height: 18,
                        borderRadius: 99,
                        border: "none",
                        cursor: locked || !sourceInWorkspace ? "not-allowed" : "pointer",
                        background: sourceIncluded ? "#f59e0b" : C.borderMid,
                        position: "relative",
                        transition: "all 0.18s",
                        flexShrink: 0,
                        opacity: locked || !sourceInWorkspace ? 0.6 : 1,
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: 2,
                          left: sourceIncluded ? 18 : 2,
                          width: 14,
                          height: 14,
                          borderRadius: "50%",
                          background: "#fff",
                          transition: "left 0.18s",
                          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
                        }}
                      />
                    </button>
                    {ree._sourceAvailable && (
                      <button
                        type="button"
                        disabled={locked}
                        onClick={onRemoveWorkspaceSource}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          width: "fit-content",
                          padding: "6px 10px",
                          borderRadius: 6,
                          border: "1px solid #fecaca",
                          background: "#fef2f2",
                          color: "#b91c1c",
                          fontSize: 12,
                          fontFamily: F.sans,
                          fontWeight: 600,
                          cursor: locked ? "not-allowed" : "pointer",
                          opacity: locked ? 0.6 : 1,
                        }}
                      >
                        {Ic.x(12)} Remove source from workspace
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                  {sourceIncluded
                    ? "Original source snapshot will be packaged into the final REE archive (workspace edits are excluded)."
                    : "Source files stay in workspace only and are excluded from the final REE archive."}
                </div>
              </div>
            </FieldRow>
          </FieldSection>

          {/* Next step nudge */}
          <div style={{ padding: "0 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={PAGE.SOURCE} badges={badges} onGo={onGoService} />
          </div>
        </div>
      </div>

      <FieldTipsSidebar
        tipFields={["origin_url", "source_type", "_sourceAcquiredBy", "_sourceAvailable"]}
        focusedField={focusedField}
        onClear={() => setFocusedField(null)}
        generalTips={[
          "Bring source code into the local workspace before any downstream step.",
          "Choose one acquisition path (download from origin or upload archive) and keep it consistent.",
        ]}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE: Metadata Entry
// ══════════════════════════════════════════════════════════════════════════════
interface PageMetadataEntryProps {
  ree: Ree;
  onChange: (ree: Ree) => void;
  locked: boolean;
  setLocked: (locked: boolean) => void;
  badges: Badges;
  onGoService: (key: string) => void;
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}
function PageMetadataEntry({
  ree,
  onChange,
  locked,
  setLocked,
  badges,
  onGoService,
  focusedField,
  setFocusedField,
}: PageMetadataEntryProps) {
  const set = (k: string, v: unknown) => onChange({ ...ree, [k]: v });
  const focus = (key: string) => setFocusedField(key);

  useEffect(() => {
    if (focusedField) {
      const el = document.getElementById(`field-${focusedField}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [focusedField]);

  const fieldUsedBy = (fieldKey: string): Service[] =>
    [EVALUATE_SVC, ...SERVICES].filter((s) => svcReadableFields(s.key).includes(fieldKey));

  const identityFilled = [ree.name].filter(Boolean).length;
  const hardwareFilled = Object.values(ree.hardware_description).filter((v) => v.trim?.()).length;

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0, overflow: "hidden" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 28, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: 0.5,
                textTransform: "uppercase",
                fontFamily: F.sans,
                color: C.textMuted,
              }}
            >
              Fields
            </h2>
          </div>
          {locked ? (
            <button
              type="button"
              onClick={() => setLocked(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                background: "#fef3c7",
                border: "1px solid #fde68a",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontFamily: F.sans,
                color: "#92400e",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {Ic.unlock(13)} Unlock fields
            </button>
          ) : null}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <FieldSection
            title="Identity"
            icon={Ic.package()}
            filledCount={identityFilled}
            totalCount={1}
          >
            <FieldRow
              fieldKey="name"
              required
              locked={locked}
              usedBy={fieldUsedBy("name")}
              onFocus={() => focus("name")}
              active={focusedField === "name"}
            >
              <input
                disabled={locked}
                value={ree.name}
                onChange={(e) => set("name", e.target.value)}
                onFocus={() => focus("name")}
                placeholder="my-project-v1.0"
                style={inp(locked)}
              />
            </FieldRow>
          </FieldSection>

          <FieldSection
            title="Hardware"
            icon={Ic.chip()}
            subtitle="target machine specification"
            filledCount={hardwareFilled > 0 ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="hardware_description"
              locked={locked}
              usedBy={fieldUsedBy("hardware_description")}
              onFocus={() => focus("hardware_description")}
              active={focusedField === "hardware_description"}
            >
              <div style={{ padding: "12px 0", display: "flex", flexDirection: "column", gap: 6 }}>
                {Object.entries(ree.hardware_description).map(([k, v], i) => (
                  <div key={i} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      disabled={locked}
                      value={k}
                      onChange={(e) => {
                        const ent = Object.entries(ree.hardware_description);
                        ent[i] = [e.target.value, v];
                        onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                      }}
                      placeholder="key"
                      style={{ ...inp(locked, { width: "auto", fontSize: 14 }), flex: "0 0 36%" }}
                    />
                    <span style={{ color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>:</span>
                    <input
                      disabled={locked}
                      value={v}
                      onChange={(e) => {
                        const ent = Object.entries(ree.hardware_description);
                        ent[i] = [k, e.target.value];
                        onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                      }}
                      placeholder="value"
                      style={{ ...inp(locked, { width: "auto", fontSize: 14 }), flex: 1 }}
                    />
                    {!locked && (
                      <button
                        type="button"
                        onClick={() => {
                          const ent = Object.entries(ree.hardware_description).filter(
                            (_, j) => j !== i,
                          );
                          onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                        }}
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: C.textMuted,
                          padding: "4px",
                          display: "flex",
                          borderRadius: 5,
                          flexShrink: 0,
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = "#dc2626";
                          e.currentTarget.style.background = "#fef2f2";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = C.textMuted;
                          e.currentTarget.style.background = "none";
                        }}
                      >
                        {Ic.x()}
                      </button>
                    )}
                  </div>
                ))}
                {!locked && (
                  <button
                    type="button"
                    onClick={() => {
                      const ent = [...Object.entries(ree.hardware_description), ["", ""]];
                      onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 10px",
                      background: "transparent",
                      border: `1.5px dashed ${C.borderMid}`,
                      borderRadius: 7,
                      cursor: "pointer",
                      fontSize: 13,
                      fontFamily: F.sans,
                      color: C.textMuted,
                      transition: "border-color 0.14s,color 0.14s",
                      marginTop: 4,
                      width: "fit-content",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = C.accent;
                      e.currentTarget.style.color = C.accent;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = C.borderMid;
                      e.currentTarget.style.color = C.textMuted;
                    }}
                  >
                    {Ic.plus()} Add field
                  </button>
                )}
              </div>
            </FieldRow>
          </FieldSection>

          <div style={{ padding: "0 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={PAGE.METADATA} badges={badges} onGo={onGoService} />
          </div>
        </div>
      </div>

      <FieldTipsSidebar
        tipFields={["name", "hardware_description"]}
        focusedField={focusedField}
        onClear={() => setFocusedField(null)}
        generalTips={[
          "Capture essential project and hardware context for reproducibility.",
          "Use stable, descriptive values so builds can be interpreted and repeated later.",
        ]}
      />
    </div>
  );
}

// ── Next-step nudge — contextual "what to do next" banner ────────────────────
// stepKey: current page key; badges: completed badge map; onGo: navigate fn
interface NextStepNudgeProps {
  stepKey: string;
  badges: Badges;
  onGo: (key: string) => void;
}
function NextStepNudge({ stepKey, badges, onGo }: NextStepNudgeProps) {
  const STEPS = [
    { key: PAGE.SOURCE, nextKey: PAGE.METADATA, nextLabel: "Provide Metadata", cond: () => true },
    { key: PAGE.METADATA, nextKey: "evaluate", nextLabel: "Evaluate", cond: () => true },
    { key: "evaluate", nextKey: "build", nextLabel: "Build Runtime", cond: () => true },
    { key: "build", nextKey: "sbom", nextLabel: "Generate SBOM", cond: () => true },
    { key: "sbom", nextKey: "activation", nextLabel: "Test Activation", cond: () => true },
    { key: "activation", nextKey: "archive", nextLabel: "Deposit & Share", cond: () => true },
    { key: "archive", nextKey: "seal", nextLabel: "Seal", cond: () => true },
    { key: "seal", nextKey: null, nextLabel: null, cond: () => false },
  ];
  const step = STEPS.find((s) => s.key === stepKey);
  if (!step || !step.nextKey || !step.nextLabel) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "9px 14px",
        background: C.accentBg,
        border: `1px solid ${C.accentBorder}`,
        borderRadius: 9,
        marginBottom: 20,
        animation: "fadeUp 0.2s ease",
      }}
    >
      <span style={{ color: C.accent, display: "flex", flexShrink: 0 }}>{Ic.chevR()}</span>
      <span style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans, flex: 1 }}>
        Next step:
      </span>
      <button
        type="button"
        onClick={() => onGo(step.nextKey)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          padding: "5px 12px",
          borderRadius: 6,
          border: "none",
          background: C.accent,
          color: "#fff",
          fontSize: 13,
          fontWeight: 600,
          fontFamily: F.sans,
          cursor: "pointer",
          flexShrink: 0,
          transition: "background 0.13s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#1d4ed8")}
        onMouseLeave={(e) => (e.currentTarget.style.background = C.accent)}
      >
        {step.nextLabel} →
      </button>
    </div>
  );
}

// Which script fields does each service actually execute?
const SVC_SCRIPT_FIELDS: Record<
  string,
  Array<{ label: string; fieldKey: keyof Ree; scriptKind: "build" | "validate" }>
> = {
  build: [{ label: "Build script", fieldKey: "build_runtime_script", scriptKind: "build" }],
  activation: [
    { label: "Activation script", fieldKey: "activation_script", scriptKind: "validate" },
  ],
};

interface ServicePageProps {
  svc: Service;
  ree: Ree;
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  badge: ServiceBadge | null;
  ts: string | undefined;
  onRun: (key: string, params: Record<string, unknown>) => void;
  onGoFields: () => void;
  badges: Badges;
  onGo: (key: string) => void;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  onReeChange?: (ree: Ree) => void;
  missing: ServiceRequire[];
  params: Record<string, unknown>;
  setParam: (key: string, value: unknown) => void;
}

interface ServicePageHeaderProps {
  svc: Service;
  icon: JSX.Element;
  title: string;
  subtitle: string;
  runDone: boolean;
  badge: ServiceBadge | null;
  ts?: string;
  timestampPrefix?: string;
  missingCount: number;
  onGoFields: () => void;
}

function ServicePageHeader({
  svc,
  icon,
  title,
  subtitle,
  runDone,
  badge,
  ts,
  timestampPrefix = "Last run",
  missingCount,
  onGoFields,
}: ServicePageHeaderProps) {
  return (
    <div
      style={{
        flexShrink: 0,
        padding: "16px 28px 14px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(255,255,255,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${svc.color}18`,
          color: svc.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text, letterSpacing: -0.2 }}>
            {title}
          </span>
          {runDone && badge && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: badge.color,
                background: badge.bg,
                border: `1px solid ${badge.color}40`,
                borderRadius: 99,
                padding: "2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {Ic.check(10)} {badge.label}
            </span>
          )}
          {missingCount > 0 && (
            <span
              style={{
                fontSize: 11,
                color: "#dc2626",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 99,
                padding: "2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 4,
                cursor: "pointer",
              }}
              onClick={onGoFields}
            >
              {Ic.info(10)} {missingCount} missing field{missingCount > 1 ? "s" : ""} ← fix
            </span>
          )}
        </div>
        <div style={{ fontSize: 12, color: C.textMuted, marginTop: 1 }}>{subtitle}</div>
      </div>
      {runDone && ts && (
        <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
          {timestampPrefix}{" "}
          {new Date(ts).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      )}
    </div>
  );
}

interface ServiceActionSectionProps {
  color: string;
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  idleLabel: string;
  runningLabel: string;
  doneLabel?: string;
  helperText: string;
  onRun: () => void;
}

function ServiceActionSection({
  color,
  running,
  runDone,
  disabled,
  idleLabel,
  runningLabel,
  doneLabel = "Re-run",
  helperText,
  onRun,
}: ServiceActionSectionProps) {
  const buttonLabel = running ? runningLabel : runDone ? doneLabel : idleLabel;
  return (
    <div
      style={{ padding: "20px 24px 16px", flexShrink: 0, borderBottom: `1px solid ${C.border}` }}
    >
      <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Action</div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            padding: "8px 18px",
            background: disabled ? `${color}22` : color,
            border: "none",
            borderRadius: 8,
            cursor: disabled ? "default" : "pointer",
            fontSize: 13,
            fontWeight: 700,
            color: disabled ? color : "#fff",
            fontFamily: F.sans,
            transition: "all 0.15s",
          }}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : Ic.play(14)}
          </span>
          {buttonLabel}
        </button>
        <div style={{ fontSize: 11, color: C.textMuted }}>{helperText}</div>
      </div>
    </div>
  );
}

function PageGenerateSBOM({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  onFilesChange,
  onReeChange,
  missing,
  params,
}: ServicePageProps) {
  const sbomColor = svc.color;
  const rt = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
  const isTb = rt && /\.(tar\.gz|tgz)$/i.test(rt);
  const hasSbom = !!(ree.sbom && ree.sbom !== "__skipped__");
  const sbomNode = hasSbom ? findFileByPath(files || [], ree.sbom) : null;
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const sbomScripts = SVC_SCRIPT_FIELDS[svc.key] || [];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      {/* Top strip */}
      <ServicePageHeader
        svc={svc}
        icon={Ic.package(18)}
        title="Generate SBOM"
        subtitle="Generate a machine-readable SBOM from the runtime image/tarball"
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {/* Step 1: Runtime input */}
          <div
            style={{
              padding: "20px 24px 16px",
              flexShrink: 0,
              borderBottom: `1px solid ${C.border}`,
              ...tipTargetSectionStyle(focusedField === "runtime"),
            }}
            onClick={() => setFocusedField("runtime")}
            onMouseEnter={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={S_SECTION_LABEL}>Step 1: Runtime Input</div>
              {tipTargetChip(focusedField === "runtime")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  background: rt ? "#ecfeff" : C.surfaceAlt,
                  border: `1.5px solid ${rt ? `${sbomColor}50` : C.border}`,
                  borderRadius: 9,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 7,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: `${rt ? sbomColor : C.textMuted}18`,
                  }}
                >
                  <span style={{ color: rt ? sbomColor : C.textMuted, display: "flex" }}>
                    {isTb ? Ic.archive(14) : Ic.cpu(14)}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: 0.8,
                      fontFamily: F.sans,
                      textTransform: "uppercase",
                      color: rt ? sbomColor : C.textMuted,
                      opacity: 0.7,
                      marginBottom: 1,
                    }}
                  >
                    Scan target · ree.runtime
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      fontFamily: F.mono,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: rt ? sbomColor : C.textMuted,
                    }}
                  >
                    {rt || (
                      <span style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11 }}>
                        not set — set a runtime in the Build Runtime step first
                      </span>
                    )}
                  </div>
                </div>
                {rt && (
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      fontWeight: 700,
                      color: sbomColor,
                      background: `${sbomColor}12`,
                      border: `1px solid ${sbomColor}40`,
                      borderRadius: 4,
                      padding: "2px 7px",
                      flexShrink: 0,
                    }}
                  >
                    {isTb ? "TARBALL" : "IMAGE"}
                  </span>
                )}
              </div>

              {!rt && (
                <button
                  type="button"
                  onClick={() => onGo(PAGE.BUILD)}
                  style={{
                    width: "fit-content",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: sbomColor,
                    background: `${sbomColor}12`,
                    border: `1px solid ${sbomColor}40`,
                    borderRadius: 6,
                    padding: "5px 10px",
                    cursor: "pointer",
                    fontWeight: 600,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.96)")}
                  onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                >
                  {Ic.chevR(12)} Go to Build Runtime
                </button>
              )}
            </div>
          </div>

          <ServiceActionSection
            color={sbomColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Generate SBOM"
            runningLabel="Generating…"
            doneLabel="Regenerate SBOM"
            helperText="Generate an SPDX JSON SBOM from the selected runtime."
            onRun={() => onRun(svc.key, params)}
          />

          {/* Step 2: Produced SBOM */}
          <div
            style={{
              padding: "16px 24px",
              borderBottom: `1px solid ${C.border}`,
              flexShrink: 0,
              ...tipTargetSectionStyle(focusedField === "sbom"),
            }}
            onClick={() => setFocusedField("sbom")}
            onMouseEnter={(e) => {
              if (focusedField === "sbom") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "sbom") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <div style={S_SECTION_LABEL}>Step 2: Produced SBOM</div>
              {tipTargetChip(focusedField === "sbom")}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 14px",
                background: hasSbom ? "#f0fdf4" : C.surfaceAlt,
                border: `1.5px solid ${hasSbom ? "#bbf7d0" : C.border}`,
                borderRadius: 9,
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 7,
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: hasSbom ? "#dcfce7" : `${C.border}40`,
                }}
              >
                <span style={{ color: hasSbom ? "#16a34a" : C.textMuted, display: "flex" }}>
                  {Ic.package(14)}
                </span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: 0.8,
                    fontFamily: F.sans,
                    textTransform: "uppercase",
                    color: hasSbom ? "#16a34a" : C.textMuted,
                    opacity: 0.7,
                    marginBottom: 1,
                  }}
                >
                  ree.sbom
                </div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    color: hasSbom ? "#15803d" : C.textMuted,
                  }}
                >
                  {hasSbom ? (
                    ree.sbom
                  ) : (
                    <span style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11 }}>
                      not set — click Generate SBOM
                    </span>
                  )}
                </div>
              </div>
              {hasSbom && (
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: F.sans,
                    fontWeight: 700,
                    color: "#16a34a",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 4,
                    padding: "2px 7px",
                    flexShrink: 0,
                  }}
                >
                  SET
                </span>
              )}
            </div>

            {hasSbom ? (
              (() => {
                if (!sbomNode)
                  return (
                    <div style={{ color: C.textMuted }}>
                      SBOM file was set but is not present in files.
                    </div>
                  );
                let pkgCount = null;
                try {
                  pkgCount = JSON.parse(sbomNode.content)?.packages?.length ?? null;
                } catch {}
                return (
                  <div>
                    <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>SBOM Preview</div>
                    <div
                      style={{
                        border: `1px solid ${sbomColor}20`,
                        borderRadius: 10,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "10px 14px",
                          background: `${sbomColor}08`,
                          borderBottom: `1px solid ${sbomColor}20`,
                        }}
                      >
                        <span style={{ color: sbomColor, display: "flex" }}>{Ic.file(13)}</span>
                        <span
                          style={{
                            fontSize: 13,
                            fontFamily: F.mono,
                            fontWeight: 700,
                            color: sbomColor,
                            flex: 1,
                          }}
                        >
                          {ree.sbom}
                        </span>
                        {pkgCount !== null && (
                          <span
                            style={{
                              fontSize: 11,
                              fontFamily: F.sans,
                              color: sbomColor,
                              background: `${sbomColor}15`,
                              border: `1px solid ${sbomColor}30`,
                              borderRadius: 10,
                              padding: "1px 8px",
                            }}
                          >
                            {pkgCount} package{pkgCount !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          background: "#0d1117",
                          padding: "14px 16px",
                          maxHeight: 340,
                          overflowY: "auto",
                        }}
                      >
                        <pre
                          style={{
                            margin: 0,
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: "#7ee787",
                            lineHeight: 1.6,
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-all",
                          }}
                        >
                          {sbomNode.content}
                        </pre>
                      </div>
                    </div>
                  </div>
                );
              })()
            ) : (
              <div style={{ color: C.textMuted }}>No SBOM generated yet.</div>
            )}
          </div>

          {sbomScripts.length > 0 && (
            <div style={{ padding: "16px 24px 0", flexShrink: 0 }}>
              <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
              {sbomScripts.map((sf) => (
                <ScriptPanel
                  key={sf.fieldKey}
                  scriptKind={sf.scriptKind || null}
                  fieldKey={sf.fieldKey}
                  files={files || MOCK_FILES}
                  onFilesChange={onFilesChange}
                  ree={ree}
                  onReeChange={onReeChange}
                />
              ))}
            </div>
          )}

          {/* Log */}
          <div
            style={{
              padding: "4px 24px 24px",
              flex: 1,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }}
          >
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
          </div>

          {/* Next step nudge */}
          <div style={{ padding: "0 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={PAGE.SBOM} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["runtime", "sbom"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
          generalTips={[
            "Generate a machine-readable inventory of software in the runtime.",
            "Run this after runtime is available so the SBOM reflects what is actually executed.",
          ]}
        />
      </div>
    </div>
  );
}

function PageTestActivation({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  onFilesChange,
  onReeChange,
  missing,
  params,
  setParam,
}: ServicePageProps) {
  const asLabel = FIELD_META["activation_script"]?.label || "Activation script";
  const buildColor = svc?.color || "#ef4444";
  const [focusedField, setFocusedField] = useState<string | null>(null);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      {/* Top strip */}
      <ServicePageHeader
        svc={svc}
        icon={Ic.play(18)}
        title={svc?.label || "Test activation"}
        subtitle="Run the activation test script to verify the runtime loads and activates correctly"
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {/* Fields */}
          <div
            style={{
              padding: "20px 24px 16px",
              flexShrink: 0,
              borderBottom: `1px solid ${C.border}`,
              ...tipTargetSectionStyle(focusedField === "activation_script"),
            }}
            onClick={() => setFocusedField("activation_script")}
            onMouseEnter={(e) => {
              if (focusedField === "activation_script") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "activation_script") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={S_SECTION_LABEL}>Fields</div>
              {tipTargetChip(focusedField === "activation_script")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{ fontSize: 12, fontWeight: 600, color: C.textMid, fontFamily: F.sans }}
                  >
                    {asLabel}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: "#ef4444",
                      fontWeight: 700,
                      fontFamily: F.sans,
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      borderRadius: 3,
                      padding: "1px 4px",
                    }}
                  >
                    required
                  </span>
                </div>
                <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                  Shell script that loads the runtime and verifies the environment activates
                  correctly
                </div>
                <FilePicker
                  disabled={false}
                  value={ree.activation_script}
                  onChange={(v) => onReeChange?.({ ...ree, activation_script: v })}
                  files={files || MOCK_FILES}
                  placeholder="activation_test.sh"
                  filterFn={(p) => /\.sh$/i.test(p)}
                />
              </div>
            </div>
          </div>

          <ServiceActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Run activation"
            runningLabel="Running…"
            helperText="Runs the activation test script in the runtime environment."
            onRun={() => onRun && onRun(PAGE.ACTIVATION, params)}
          />

          {/* Scripts */}
          <div style={{ padding: "16px 24px 0", flexShrink: 0 }}>
            <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
            {SVC_SCRIPT_FIELDS["activation"]?.map((sf) => (
              <ScriptPanel
                key={sf.fieldKey}
                scriptKind={sf.scriptKind || null}
                fieldKey={sf.fieldKey}
                files={files || MOCK_FILES}
                onFilesChange={onFilesChange}
                ree={ree}
                onReeChange={onReeChange}
                saveToWorkspaceOnly
              />
            ))}
          </div>

          {/* Log */}
          <div
            style={{
              padding: "4px 24px 24px",
              flex: 1,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }}
          >
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
          </div>

          {/* Next step nudge */}
          <div style={{ padding: "0 24px 24px", flexShrink: 0 }}>
            <NextStepNudge
              stepKey={PAGE.ACTIVATION}
              badges={badges || {}}
              onGo={onGo || (() => {})}
            />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["activation_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
          generalTips={[
            "Verify the built runtime can start and activate cleanly.",
            "Treat activation as a gate before archival to avoid preserving broken environments.",
          ]}
        />
      </div>
    </div>
  );
}

// ── Dependency manifest scanner & parser ──────────────────────────────────────
// Each parser returns [{ name, version, raw, pinned }]
// pinned: "exact" | "range" | "none"

function parsePinStatus(version: string | null | undefined): PinStatus {
  if (!version) return "none";
  if (/^[=~^]?[0-9]/.test(version) && version.includes("==")) return "exact";
  if (/[=<>~^]/.test(version)) return "range";
  if (/^[0-9]/.test(version)) return "exact"; // bare version like "3.11.7"
  return "none";
}

const DEP_PARSERS = {
  // requirements.txt — one package per line: name[extras]specifier  # comment
  "requirements.txt": (content) => {
    const pkgs = [];
    for (const raw of content.split("\n")) {
      const line = raw.replace(/#.*$/, "").trim();
      if (!line || line.startsWith("-") || line.startsWith("http")) continue;
      const m = line.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*]+)?$/);
      if (!m) continue;
      const name = m[1];
      const version = (m[3] || "").trim() || null;
      pkgs.push({ name, version, raw: line, pinned: parsePinStatus(version) });
    }
    return pkgs;
  },
  // pyproject.toml — parse [project].dependencies array entries
  "pyproject.toml": (content) => {
    const pkgs = [];
    const inDeps = { value: false };
    for (const raw of content.split("\n")) {
      const line = raw.trim();
      if (line === "[project.dependencies]" || line === "dependencies = [") {
        inDeps.value = true;
        continue;
      }
      if (inDeps.value && line.startsWith("[") && !line.startsWith("dependencies")) {
        inDeps.value = false;
      }
      const quoted = line.match(/^["']([^"']+)["'],?$/);
      const src = quoted?.[1] || (inDeps.value ? line.replace(/,$/, "") : null);
      if (!src) continue;
      const m = src.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*"']+)?$/);
      if (!m) continue;
      const name = m[1];
      const version = (m[3] || "").replace(/['"]/g, "").trim() || null;
      pkgs.push({ name, version, raw: src, pinned: parsePinStatus(version) });
    }
    return pkgs;
  },
  // environment.yml — conda dependencies list
  "environment.yml": (content) => {
    const pkgs = [];
    let inDeps = false;
    let inPip = false;
    for (const raw of content.split("\n")) {
      const line = raw.trim();
      if (line === "dependencies:") {
        inDeps = true;
        continue;
      }
      if (inDeps && line === "- pip:") {
        inPip = true;
        continue;
      }
      if (!inDeps) continue;
      if (line.startsWith("-") && !line.startsWith("- pip:")) {
        const entry = line
          .slice(1)
          .trim()
          .replace(/^["']|["']$/g, "");
        // conda entries use = not ==
        const m = entry.match(/^([A-Za-z0-9_\-.]+)\s*([=<>!~][=<>!~\s0-9.*]+)?$/);
        if (!m) continue;
        const name = m[1];
        const rawVer = (m[2] || "").trim() || null;
        // normalise conda single-= to ==
        const version = rawVer ? rawVer.replace(/^=(?!=)/, "==") : null;
        pkgs.push({
          name,
          version,
          raw: entry,
          pinned: parsePinStatus(version),
          ecosystem: inPip ? "pip" : "conda",
        });
      }
    }
    return pkgs;
  },
  // package.json
  "package.json": (content) => {
    try {
      const obj = JSON.parse(content);
      const pkgs = [];
      const add = (deps: Record<string, string> | undefined, dev: boolean) => {
        for (const [name, version] of Object.entries(deps || {})) {
          pkgs.push({
            name,
            version,
            raw: `${name}: ${version}`,
            pinned: parsePinStatus(version),
            dev,
          });
        }
      };
      add(obj.dependencies, false);
      add(obj.devDependencies, true);
      return pkgs;
    } catch {
      return [];
    }
  },
  // Pipfile
  Pipfile: (content) => {
    const pkgs = [];
    let inSection = false;
    for (const raw of content.split("\n")) {
      const line = raw.trim();
      if (line === "[packages]" || line === "[dev-packages]") {
        inSection = true;
        continue;
      }
      if (line.startsWith("[") && line !== "[packages]" && line !== "[dev-packages]") {
        inSection = false;
      }
      if (!inSection) continue;
      const m = line.match(/^([A-Za-z0-9_\-.]+)\s*=\s*["']([^"']*)["']/);
      if (!m) continue;
      pkgs.push({
        name: m[1],
        version: m[2] === "*" ? null : m[2],
        raw: line,
        pinned: parsePinStatus(m[2] === "*" ? null : m[2]),
      });
    }
    return pkgs;
  },
};

// Recognise manifest files by name
function getManifestParser(filename: string): ((content: string) => DepPackage[]) | null {
  const lower = filename.toLowerCase();
  if (lower === "requirements.txt" || /^requirements[-_].+\.txt$/.test(lower))
    return DEP_PARSERS["requirements.txt"];
  if (lower === "pyproject.toml") return DEP_PARSERS["pyproject.toml"];
  if (lower === "environment.yml" || lower === "environment.yaml")
    return DEP_PARSERS["environment.yml"];
  if (lower === "package.json") return DEP_PARSERS["package.json"];
  if (lower === "pipfile") return DEP_PARSERS["Pipfile"];
  return null;
}

// Ecosystem colour palette
interface EcoMeta {
  label: string;
  color: string;
  bg: string;
}
const ECO_META: Record<string, EcoMeta> = {
  pip: { label: "pip", color: "#3b82f6", bg: "#eff6ff" },
  conda: { label: "conda", color: "#22c55e", bg: "#f0fdf4" },
  npm: { label: "npm", color: "#dc2626", bg: "#fef2f2" },
  toml: { label: "toml", color: "#8b5cf6", bg: "#f5f3ff" },
  dev: { label: "dev", color: "#f59e0b", bg: "#fffbeb" },
};

interface PinMeta {
  label: string;
  color: string;
  bg: string;
  border: string;
}
const PIN_META: Record<PinStatus, PinMeta> = {
  exact: { label: "pinned", color: "#16a34a", bg: "#dcfce7", border: "#86efac" },
  range: { label: "range", color: "#d97706", bg: "#fef3c7", border: "#fcd34d" },
  none: { label: "unpinned", color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
};

function scanDependencies(nodes: FileTreeNode[], path = ""): DepGroup[] {
  const results = []; // [{ file, path, ecosystem, packages }]
  for (const node of nodes || []) {
    const fullPath = path ? `${path}/${node.name}` : node.name;
    if (node.type === "folder") {
      results.push(...scanDependencies(node.children, fullPath));
    } else {
      const parser = getManifestParser(node.name);
      if (parser) {
        const lower = node.name.toLowerCase();
        const eco =
          lower === "package.json"
            ? "npm"
            : lower === "pyproject.toml"
              ? "toml"
              : lower.includes("environment")
                ? "conda"
                : "pip";
        const packages = parser(node.content || "");
        if (packages.length > 0) {
          results.push({ file: node.name, path: fullPath, ecosystem: eco, packages });
        }
      }
    }
  }
  return results;
}

// ── DependencyPanel ───────────────────────────────────────────────────────────
interface DependencyPanelProps {
  depGroups: DepGroup[];
}
function DependencyPanel({ depGroups }: DependencyPanelProps) {
  const [openGroups, setOpenGroups] = useState(() =>
    Object.fromEntries(depGroups.map((g) => [g.path, true])),
  );
  const [filter, setFilter] = useState("all"); // all | exact | range | none

  const totalPkgs = depGroups.reduce((s, g) => s + g.packages.length, 0);
  const pinnedCount = depGroups.reduce(
    (s, g) => s + g.packages.filter((p) => p.pinned === "exact").length,
    0,
  );
  const rangeCount = depGroups.reduce(
    (s, g) => s + g.packages.filter((p) => p.pinned === "range").length,
    0,
  );
  const noneCount = depGroups.reduce(
    (s, g) => s + g.packages.filter((p) => p.pinned === "none").length,
    0,
  );

  const toggle = (path: string) => setOpenGroups((o) => ({ ...o, [path]: !o[path] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, minHeight: 0 }}>
      {/* ── Summary row ── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {[
          {
            key: "all",
            label: `${totalPkgs} total`,
            color: C.textMid,
            bg: C.surfaceAlt,
            border: C.border,
          },
          { key: "exact", label: `${pinnedCount} pinned`, ...PIN_META.exact },
          { key: "range", label: `${rangeCount} range`, ...PIN_META.range },
          { key: "none", label: `${noneCount} unpinned`, ...PIN_META.none },
        ].map((s) => (
          <button
            type="button"
            key={s.key}
            onClick={() => setFilter(s.key)}
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              fontWeight: 600,
              color: s.color,
              background: filter === s.key ? s.bg : "transparent",
              border: `1.5px solid ${filter === s.key ? s.border : C.border}`,
              borderRadius: 99,
              padding: "3px 10px",
              cursor: "pointer",
              transition: "all 0.12s",
            }}
            onMouseEnter={(e) => {
              if (filter !== s.key) {
                e.currentTarget.style.background = s.bg;
                e.currentTarget.style.borderColor = s.border;
              }
            }}
            onMouseLeave={(e) => {
              if (filter !== s.key) {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.borderColor = C.border;
              }
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* ── File groups ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {depGroups.map((group) => {
          const visiblePkgs =
            filter === "all" ? group.packages : group.packages.filter((p) => p.pinned === filter);
          if (visiblePkgs.length === 0 && filter !== "all") return null;
          const ecoMeta = ECO_META[group.ecosystem] || ECO_META.pip;
          const isOpen = openGroups[group.path] !== false;
          const groupPinned = group.packages.filter((p) => p.pinned === "exact").length;
          const groupUnpinned = group.packages.filter((p) => p.pinned === "none").length;

          return (
            <div
              key={group.path}
              style={{
                border: `1.5px solid ${ecoMeta.color}35`,
                borderRadius: 10,
                overflow: "hidden",
                background: "rgba(255,255,255,0.7)",
              }}
            >
              {/* Group header */}
              <button
                type="button"
                onClick={() => toggle(group.path)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 12px",
                  background: `${ecoMeta.color}12`,
                  borderTopWidth: 0,
                  borderLeftWidth: 0,
                  borderRightWidth: 0,
                  borderBottomWidth: isOpen ? 1 : 0,
                  borderBottomStyle: "solid",
                  borderBottomColor: isOpen ? `${ecoMeta.color}25` : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background 0.12s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = `${ecoMeta.color}1e`)}
                onMouseLeave={(e) => (e.currentTarget.style.background = `${ecoMeta.color}12`)}
              >
                <span style={{ display: "flex", color: ecoMeta.color }}>{Ic.file(13)}</span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    color: ecoMeta.color,
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {group.path}
                </span>
                {/* eco badge */}
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: ecoMeta.color,
                    background: ecoMeta.bg,
                    border: `1px solid ${ecoMeta.color}40`,
                    borderRadius: 99,
                    padding: "1px 6px",
                    fontFamily: F.sans,
                    flexShrink: 0,
                  }}
                >
                  {ecoMeta.label}
                </span>
                {/* mini stats */}
                <span
                  style={{
                    fontSize: 10,
                    color: "#16a34a",
                    fontFamily: F.mono,
                    flexShrink: 0,
                    marginLeft: 4,
                  }}
                >
                  {groupPinned}✓
                </span>
                {groupUnpinned > 0 && (
                  <span
                    style={{ fontSize: 10, color: "#dc2626", fontFamily: F.mono, flexShrink: 0 }}
                  >
                    {groupUnpinned}✗
                  </span>
                )}
                <span style={{ display: "flex", color: C.textMuted, marginLeft: 4 }}>
                  {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
                </span>
              </button>

              {/* Package rows */}
              {isOpen && (
                <div>
                  {/* Column headers */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 130px 80px",
                      gap: 0,
                      padding: "4px 12px",
                      background: C.surfaceAlt,
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    {["Package", "Version / Constraint", "Status"].map((h) => (
                      <span
                        key={h}
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: 0.8,
                          color: C.textMuted,
                          textTransform: "uppercase",
                          fontFamily: F.sans,
                        }}
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                  {(filter === "all" ? group.packages : visiblePkgs).map((pkg, i) => {
                    const pm = PIN_META[pkg.pinned] || PIN_META.none;
                    return (
                      <div
                        key={i}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 130px 80px",
                          gap: 0,
                          padding: "5px 12px",
                          borderBottom: `1px solid ${C.border}`,
                          background: i % 2 === 0 ? "transparent" : "#fafbfd",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 0 }}>
                          {pkg.dev && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.dev.color,
                                background: ECO_META.dev.bg,
                                border: `1px solid ${ECO_META.dev.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              dev
                            </span>
                          )}
                          {pkg.ecosystem === "pip" && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.pip.color,
                                background: ECO_META.pip.bg,
                                border: `1px solid ${ECO_META.pip.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              pip
                            </span>
                          )}
                          <span
                            style={{
                              fontSize: 12,
                              fontFamily: F.mono,
                              color: C.text,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pkg.name}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: pkg.version ? C.textMid : C.textMuted,
                            fontStyle: pkg.version ? "normal" : "italic",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            alignSelf: "center",
                          }}
                        >
                          {pkg.version || "—"}
                        </span>
                        <span style={{ alignSelf: "center" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: pm.color,
                              background: pm.bg,
                              border: `1px solid ${pm.border}`,
                              borderRadius: 99,
                              padding: "1px 6px",
                              fontFamily: F.sans,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pm.label}
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── File viewer card (collapsible, syntax-highlighted) ────────────────────────
interface FileViewCardProps {
  file: { path: string; name: string; content?: string };
  color: string;
  badge: string;
  icon: (size?: number) => JSX.Element;
}
function FileViewCard({ file, color, badge, icon }: FileViewCardProps) {
  const [open, setOpen] = useState(true);
  const lines = (file.content || "").split("\n");
  return (
    <div
      style={{
        border: `1.5px solid ${color}35`,
        borderRadius: 9,
        overflow: "hidden",
        marginBottom: 8,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 7,
          padding: "8px 11px",
          background: `${color}12`,
          borderBottom: open ? `1px solid ${color}22` : "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = `${color}1e`)}
        onMouseLeave={(e) => (e.currentTarget.style.background = `${color}12`)}
      >
        <span style={{ display: "flex", color, flexShrink: 0 }}>{icon(13)}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            fontFamily: F.mono,
            color,
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {file.path}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: 0.5,
            color,
            background: `${color}20`,
            border: `1px solid ${color}40`,
            borderRadius: 99,
            padding: "1px 6px",
            fontFamily: F.sans,
            flexShrink: 0,
          }}
        >
          {badge}
        </span>
        <span style={{ display: "flex", color: C.textMuted, marginLeft: 4, flexShrink: 0 }}>
          {open ? Ic.chevD(11) : Ic.chevR(11)}
        </span>
      </button>
      {open && (
        <div style={{ maxHeight: 180, overflowY: "auto", background: C.surface }}>
          {lines.map((line, i) => (
            <div key={i} style={{ display: "flex", alignItems: "baseline" }}>
              <span
                style={{
                  minWidth: 32,
                  textAlign: "right",
                  paddingRight: 10,
                  paddingLeft: 8,
                  fontSize: 10,
                  fontFamily: F.mono,
                  color: C.borderMid,
                  userSelect: "none",
                  flexShrink: 0,
                }}
              >
                {i + 1}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  lineHeight: 1.65,
                  display: "block",
                  paddingRight: 12,
                  whiteSpace: "pre",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  color: line.startsWith("#")
                    ? "#94a3b8"
                    : /^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV|EXPOSE|LABEL)\b/.test(line)
                      ? "#0369a1"
                      : /^(let|in|with|rec|if|then|else|inherit|pkgs)\b/.test(line)
                        ? "#7c3aed"
                        : line.match(/^\s*[\w-]+ =/)
                          ? "#b45309"
                          : C.text,
                }}
              >
                {line || " "}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE: EVALUATE (full-width layout with dependency detection panel)
// ══════════════════════════════════════════════════════════════════════════════
function PageEvaluate({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  missing,
  params,
  setParam,
}: ServicePageProps) {
  const depGroups = scanDependencies(files || MOCK_FILES);
  const hasRun = !!log;
  const hasScoreOutput = !!runDone;
  const sourceLoadedInWorkspace = !!ree._sourceAvailable;
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const IC = svc.IC || Ic.star;
  const level = Math.min(ree._evalLevel ?? 0, LEVELS.length - 1);
  const currentLevel = LEVELS[level];
  const standing = `${level + 1} / ${LEVELS.length}`;
  const completionPct = Math.round((level / (LEVELS.length - 1)) * 100);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      {/* ══ Header strip ══ */}
      <div
        style={{
          flexShrink: 0,
          padding: "16px 28px 14px",
          borderBottom: `1px solid ${C.border}`,
          background: "rgba(255,255,255,0.7)",
          backdropFilter: "blur(8px)",
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: `${svc.color}18`,
            color: svc.color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {IC(18)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: C.text, letterSpacing: -0.2 }}>
              {svc.label}
            </span>
            {runDone && badge && (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: badge.color,
                  background: badge.bg,
                  border: `1px solid ${badge.color}40`,
                  borderRadius: 99,
                  padding: "2px 9px",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {Ic.check(10)} {badge.label}
              </span>
            )}
            {missing.length > 0 && (
              <span
                onClick={onGoFields}
                style={{
                  fontSize: 11,
                  color: "#dc2626",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: 99,
                  padding: "2px 9px",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  cursor: "pointer",
                }}
              >
                {Ic.info(10)} {missing.length} missing field{missing.length > 1 ? "s" : ""} ← fix
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: C.textMuted, marginTop: 1 }}>{svc.desc}</div>
        </div>
        {runDone && ts && (
          <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
            Last run{" "}
            {new Date(ts).toLocaleString([], {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {/* ══ Body: left controls + log | right tips ══ */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* ── LEFT: parameters + run + log ── */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            minHeight: 0,
            padding: "24px 28px",
            display: "flex",
            flexDirection: "column",
            gap: 0,
          }}
        >
          {/* Missing requirements banner */}
          {missing.length > 0 && (
            <div
              style={{
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 10,
                padding: "12px 16px",
                marginBottom: 20,
                display: "flex",
                gap: 12,
                alignItems: "flex-start",
              }}
            >
              <span style={{ color: "#dc2626", flexShrink: 0, marginTop: 1 }}>{Ic.info()}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#dc2626", marginBottom: 5 }}>
                  Missing required fields
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
                  {missing.map((r) => (
                    <span
                      key={r.field}
                      style={{
                        fontSize: 12,
                        fontFamily: F.sans,
                        color: "#dc2626",
                        background: "#fff",
                        border: "1px solid #fecaca",
                        borderRadius: 4,
                        padding: "2px 8px",
                      }}
                    >
                      {r.label}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={onGoFields}
                  style={{
                    fontSize: 13,
                    fontFamily: F.sans,
                    color: C.accent,
                    background: "transparent",
                    border: `1px solid ${C.accentBorder}`,
                    borderRadius: 6,
                    padding: "4px 10px",
                    cursor: "pointer",
                  }}
                >
                  ← Go to Source Repo
                </button>
              </div>
            </div>
          )}

          {/* All required fields set banner */}
          {svc.requires && svc.requires.length > 0 && missing.length === 0 && (
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: 10,
                padding: "10px 14px",
                marginBottom: 20,
                display: "flex",
                gap: 8,
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <span style={{ color: "#16a34a", display: "flex", flexShrink: 0 }}>{Ic.check()}</span>
              <span style={{ fontSize: 13, color: "#16a34a", fontFamily: F.sans, fontWeight: 600 }}>
                All required fields set:
              </span>
              {svc.requires.map((r) => (
                <span
                  key={r.field}
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#16a34a",
                    background: "#dcfce7",
                    border: "1px solid #bbf7d0",
                    borderRadius: 4,
                    padding: "2px 7px",
                  }}
                >
                  {r.label}
                </span>
              ))}
            </div>
          )}

          {svc.key !== "sbom" && svc.key !== "activation" && (
            <>
              <ServiceActionSection
                color={svc.color}
                running={running}
                runDone={runDone}
                disabled={running || !sourceLoadedInWorkspace}
                idleLabel="Run"
                runningLabel="Running…"
                helperText={
                  sourceLoadedInWorkspace
                    ? "Run evaluation with the selected parameters."
                    : "Load source into workspace first. Evaluate is enabled only after source download/upload succeeds."
                }
                onRun={() => onRun(svc.key, params)}
              />

              {/* Repro level score and ladder (Evaluate output) */}
              <div
                style={{
                  background: C.surface,
                  borderTopWidth: 1,
                  borderTopStyle: "solid",
                  borderTopColor: hasScoreOutput ? `${svc.color}55` : C.border,
                  borderRightWidth: 1,
                  borderRightStyle: "solid",
                  borderRightColor: hasScoreOutput ? `${svc.color}55` : C.border,
                  borderBottomWidth: 1,
                  borderBottomStyle: "solid",
                  borderBottomColor: hasScoreOutput ? `${svc.color}55` : C.border,
                  borderRadius: 12,
                  padding: "16px 18px",
                  marginBottom: 20,
                  ...tipTargetSectionStyle(focusedField === "repro_level"),
                }}
                onClick={() => setFocusedField("repro_level")}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 10,
                  }}
                >
                  <div>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8, ...S_SECTION_LABEL }}
                    >
                      Evaluate Output · Reproducibility Score
                      {tipTargetChip(focusedField === "repro_level")}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: hasScoreOutput ? currentLevel.ink : C.textMuted,
                        marginTop: 2,
                        fontWeight: hasScoreOutput ? 600 : 500,
                      }}
                    >
                      {hasScoreOutput
                        ? `Computed from latest completed Evaluate run · Standing level ${standing}`
                        : "No Evaluate output yet. Complete a run to generate the level."}
                    </div>
                  </div>
                  <LevelBadge level={level} />
                </div>

                <div
                  style={{
                    height: 7,
                    borderRadius: 99,
                    background: C.surfaceAlt,
                    border: `1px solid ${C.border}`,
                    overflow: "hidden",
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      width: `${hasScoreOutput ? completionPct : 0}%`,
                      height: "100%",
                      background: currentLevel.color,
                      transition: "width 0.24s ease",
                    }}
                  />
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {LEVELS.map((lv, idx) => {
                    const reached = hasScoreOutput && idx <= level;
                    const active = hasScoreOutput && idx === level;
                    return (
                      <div
                        key={lv.n}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 8,
                          padding: "7px 8px",
                          borderRadius: 8,
                          border: `1px solid ${active ? `${lv.color}55` : C.border}`,
                          background: active ? lv.bg : "transparent",
                          opacity: hasScoreOutput ? 1 : 0.9,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            fontFamily: F.mono,
                            color: reached ? lv.ink : C.textMuted,
                            background: reached ? lv.bg : C.surfaceAlt,
                            border: `1px solid ${reached ? `${lv.color}55` : C.border}`,
                            borderRadius: 99,
                            padding: "1px 7px",
                            flexShrink: 0,
                            marginTop: 1,
                          }}
                        >
                          L{lv.n}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: 12,
                              fontWeight: active ? 700 : 600,
                              color: reached ? C.text : C.textMid,
                            }}
                          >
                            {lv.label}
                          </div>
                          <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                            {lv.desc}
                          </div>
                          <div
                            style={{
                              marginTop: 5,
                              display: "flex",
                              flexDirection: "column",
                              gap: 4,
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: 6,
                                padding: "4px 6px",
                                borderRadius: 6,
                                background: "#fffbeb",
                                border: "1px solid #fde68a",
                              }}
                            >
                              <span
                                style={{
                                  display: "flex",
                                  color: "#b45309",
                                  flexShrink: 0,
                                  marginTop: 1,
                                }}
                              >
                                {Ic.info(11)}
                              </span>
                              <span style={{ fontSize: 11, color: "#92400e", lineHeight: 1.35 }}>
                                {lv.problem || "No major bottleneck called out at this level."}
                              </span>
                            </div>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: 6,
                                padding: "4px 6px",
                                borderRadius: 6,
                                background: "#f0fdf4",
                                border: "1px solid #bbf7d0",
                              }}
                            >
                              <span
                                style={{
                                  display: "flex",
                                  color: "#15803d",
                                  flexShrink: 0,
                                  marginTop: 1,
                                }}
                              >
                                {Ic.check(11)}
                              </span>
                              <span style={{ fontSize: 11, color: "#166534", lineHeight: 1.35 }}>
                                {lv.fix || "No additional fix suggested at this level."}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Dependency detection */}
              <div
                style={{
                  background: C.surface,
                  borderTopWidth: 1,
                  borderTopStyle: "solid",
                  borderTopColor: C.border,
                  borderRightWidth: 1,
                  borderRightStyle: "solid",
                  borderRightColor: C.border,
                  borderBottomWidth: 1,
                  borderBottomStyle: "solid",
                  borderBottomColor: C.border,
                  borderRadius: 12,
                  padding: "16px 18px",
                  marginBottom: 20,
                  ...tipTargetSectionStyle(focusedField === "detected_dependencies"),
                }}
                onClick={() => setFocusedField("detected_dependencies")}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <div style={S_SECTION_LABEL}>Detected Dependencies</div>
                  {tipTargetChip(focusedField === "detected_dependencies")}
                  {!hasRun && (
                    <span
                      style={{
                        fontSize: 11,
                        color: C.textMuted,
                        fontStyle: "italic",
                        marginLeft: "auto",
                      }}
                    >
                      run to scan
                    </span>
                  )}
                </div>

                {hasRun ? (
                  <>
                    {depGroups.length > 0 ? (
                      <DependencyPanel depGroups={depGroups} />
                    ) : (
                      <div
                        style={{
                          border: `1.5px dashed ${C.borderMid}`,
                          borderRadius: 10,
                          padding: "16px",
                          textAlign: "center",
                          color: C.textMuted,
                          marginBottom: 12,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "center",
                            marginBottom: 6,
                            opacity: 0.4,
                          }}
                        >
                          {Ic.package(20)}
                        </div>
                        <div style={{ fontSize: 12, fontFamily: F.sans }}>
                          No manifest files found
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: C.textMuted,
                            fontFamily: F.sans,
                            marginTop: 3,
                          }}
                        >
                          Add requirements.txt, pyproject.toml, environment.yml, or package.json.
                        </div>
                      </div>
                    )}

                    {(() => {
                      let containerCount = 0;
                      let nixCount = 0;
                      const scan = (nodes) => {
                        for (const n of nodes || []) {
                          if (n.type === "folder") scan(n.children);
                          else {
                            const lo = n.name.toLowerCase();
                            if (
                              lo === "dockerfile" ||
                              lo === "containerfile" ||
                              lo.startsWith("dockerfile.") ||
                              lo.startsWith("containerfile.") ||
                              lo === "docker-compose.yml" ||
                              lo === "docker-compose.yaml"
                            )
                              containerCount += 1;
                            if (lo.endsWith(".nix")) nixCount += 1;
                          }
                        }
                      };
                      scan(files || MOCK_FILES);
                      return (
                        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <span
                            style={{
                              fontSize: 11,
                              color: "#0e7490",
                              background: "#ecfeff",
                              border: "1px solid #a5f3fc",
                              borderRadius: 99,
                              padding: "3px 10px",
                              fontFamily: F.sans,
                              fontWeight: 600,
                            }}
                          >
                            Container files: {containerCount}
                          </span>
                          <span
                            style={{
                              fontSize: 11,
                              color: "#6d28d9",
                              background: "#f5f3ff",
                              border: "1px solid #ddd6fe",
                              borderRadius: 99,
                              padding: "3px 10px",
                              fontFamily: F.sans,
                              fontWeight: 600,
                            }}
                          >
                            Nix files: {nixCount}
                          </span>
                        </div>
                      );
                    })()}
                  </>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[
                      {
                        label: "requirements.txt",
                        hint: "pip — per-package pins",
                        color: "#3b82f6",
                      },
                      { label: "pyproject.toml", hint: "pip / hatch / poetry", color: "#8b5cf6" },
                      { label: "environment.yml", hint: "conda + bioconda", color: "#22c55e" },
                      { label: "package.json", hint: "npm / yarn dependencies", color: "#dc2626" },
                      { label: "Dockerfile", hint: "container environment", color: "#0891b2" },
                      { label: "*.nix", hint: "declarative system env", color: "#7c3aed" },
                    ].map((item) => (
                      <div
                        key={item.label}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "7px 10px",
                          border: `1.5px dashed ${item.color}30`,
                          borderRadius: 8,
                          background: `${item.color}05`,
                          opacity: 0.7,
                        }}
                      >
                        <span style={{ display: "flex", color: item.color, opacity: 0.6 }}>
                          {Ic.file(12)}
                        </span>
                        <span
                          style={{
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: item.color,
                            fontWeight: 600,
                            flex: 1,
                          }}
                        >
                          {item.label}
                        </span>
                        <span style={{ fontSize: 10, color: C.textMuted, fontFamily: F.sans }}>
                          {item.hint}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Log output */}
              <div
                style={{
                  fontSize: 11,
                  letterSpacing: 1.3,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  textTransform: "uppercase",
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                Output
              </div>
              <LogPanel log={log} running={running} />

              {/* Next step nudge */}
              <div style={{ padding: "24px 24px 24px", flexShrink: 0 }}>
                <NextStepNudge stepKey={svc.key} badges={badges || {}} onGo={onGo || (() => {})} />
              </div>
            </>
          )}
        </div>

        <FieldTipsSidebar
          tipFields={["detected_dependencies", "repro_level"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose either detected dependencies or repro level to see Evaluate-specific tips."
          generalTips={[
            "Score reproducibility maturity from the repository state in workspace.",
            "Use this output to decide the next highest-impact improvement before Build.",
          ]}
        />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RuntimeOutputNode — shows build output check + "Set as runtime" action
interface RuntimeOutputNodeProps {
  expectedOutput: string;
  buildDone: boolean;
  ree: Ree;
  imageColor: string;
  files: FileTreeNode[];
}
function RuntimeOutputNode({
  expectedOutput,
  buildDone,
  ree,
  imageColor,
  files,
}: RuntimeOutputNodeProps) {
  // Treat expectedOutput always as a file path (tarball or other file).
  const isTarball = expectedOutput && /\.(tar\.gz|tgz)$/i.test(expectedOutput);
  const alreadySet = expectedOutput && ree.runtime === expectedOutput;

  const fileExists = isTarball
    ? !!(function find(nodes) {
        for (const n of nodes || []) {
          if (
            n.type === "file" &&
            (n.name === expectedOutput || expectedOutput.endsWith(`/${n.name}`))
          )
            return n;
          if (n.children) {
            const r = find(n.children);
            if (r) return r;
          }
        }
      })(files || [])
    : false;

  const state = !expectedOutput
    ? "unset"
    : !buildDone
      ? "pending"
      : fileExists
        ? "found"
        : "missing";

  const colors = {
    unset: { border: C.border, bg: C.surfaceAlt, text: C.textMuted, icon: C.textMuted },
    pending: { border: C.accentBorder, bg: C.accentBg, text: C.accent, icon: C.accent },
    found: { border: `${imageColor}60`, bg: "#ecfeff", text: imageColor, icon: imageColor },
    missing: { border: "#fca5a5", bg: "#fef2f2", text: "#dc2626", icon: "#dc2626" },
    // no image-ref state; expectedOutput is always a file path
  };
  const col = colors[state];
  const hasActionRow = state === "missing";

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: col.bg,
          border: `1.5px solid ${col.border}`,
          borderRadius: hasActionRow ? "8px 8px 0 0" : 8,
          transition: "all 0.3s",
          boxShadow: expectedOutput ? `0 0 0 3px ${col.border}30` : "none",
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: `${col.icon}18`,
          }}
        >
          <span style={{ color: col.icon, display: "flex" }}>{Ic.archive(14)}</span>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: 0.8,
              fontFamily: F.sans,
              textTransform: "uppercase",
              color: col.text,
              opacity: 0.7,
              marginBottom: 1,
            }}
          >
            {state === "unset" ? "Build output" : "Runtime file"}
          </div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              fontFamily: F.mono,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: col.text,
            }}
          >
            {expectedOutput || (
              <span
                style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11, color: C.textMuted }}
              >
                not specified
              </span>
            )}
          </div>
          {expectedOutput && (
            <div
              style={{
                fontSize: 10,
                color: col.text,
                opacity: 0.7,
                fontFamily: F.sans,
                marginTop: 1,
              }}
            >
              {state === "pending" && "will be checked after build runs"}
              {state === "found" && "✓ produced by build"}
              {state === "missing" && "✗ not found after build"}
            </div>
          )}
        </div>
        {state === "found" && (
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              color: imageColor,
              background: `${imageColor}18`,
              border: `1px solid ${imageColor}40`,
              borderRadius: 4,
              padding: "2px 7px",
              flexShrink: 0,
            }}
          >
            FOUND
          </span>
        )}
        {state === "missing" && (
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              color: "#dc2626",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: 4,
              padding: "2px 7px",
              flexShrink: 0,
            }}
          >
            NOT FOUND
          </span>
        )}
        {alreadySet && (
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              color: "#16a34a",
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: 4,
              padding: "2px 7px",
              flexShrink: 0,
            }}
          >
            SET
          </span>
        )}
      </div>

      {/* Manual setting removed: runtime is auto-detected from build output. */}

      {state === "missing" && (
        <div
          style={{
            padding: "9px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderTop: "none",
            borderRadius: "0 0 8px 8px",
          }}
        >
          <span style={{ fontSize: 11, color: "#dc2626", fontFamily: F.sans, lineHeight: 1.4 }}>
            Expected <code style={{ fontFamily: F.mono, fontSize: 10.5 }}>{expectedOutput}</code>{" "}
            but it wasn't produced. Check your build script writes to this path.
          </span>
        </div>
      )}
    </div>
  );
}

function PageBuildRuntime({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  onFilesChange,
  onReeChange,
  missing,
  params,
  setParam,
}: ServicePageProps) {
  const [expectedOutput, setExpectedOutput] = useState(() =>
    ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "",
  );
  const [showManualOverride, setShowManualOverride] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const buildColor = svc.color;
  const imageColor = "#0891b2";
  const metaRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const includeRuntime = !!ree._runtimeIncluded && !!finalRuntime;
  const finalRuntimeFile = finalRuntime
    ? findFileByPath(files || [], finalRuntime) ||
      findFileByPath(files || [], finalRuntime.split("/").pop() || "")
    : null;
  const finalRuntimeSize = finalRuntimeFile
    ? (() => {
        const m = (finalRuntimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
        if (m) return m[1];
        const b = new TextEncoder().encode(finalRuntimeFile.content || "").length;
        if (b < 1024) return `${b} B`;
        if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
        return `${(b / (1024 * 1024)).toFixed(2)} MB`;
      })()
    : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      {/* Top strip */}
      <ServicePageHeader
        svc={svc}
        icon={Ic.cpu(18)}
        title={svc.label}
        subtitle={svc.desc}
        runDone={runDone}
        badge={badge}
        ts={ts}
        timestampPrefix="Last built"
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* Scrollable body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {/* BUILD SCRIPT — First step in workflow */}
          <div
            style={{
              padding: "20px 24px 16px",
              flexShrink: 0,
              borderBottom: `1px solid ${C.border}`,
              ...tipTargetSectionStyle(focusedField === "build_runtime_script"),
            }}
            onClick={() => setFocusedField("build_runtime_script")}
            onMouseEnter={(e) => {
              if (focusedField === "build_runtime_script") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "build_runtime_script") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={S_SECTION_LABEL}>Step 1: Build Script</div>
              {tipTargetChip(focusedField === "build_runtime_script")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{ fontSize: 12, fontWeight: 600, color: C.textMid, fontFamily: F.sans }}
                >
                  Shell script
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: "#ef4444",
                    fontWeight: 700,
                    fontFamily: F.sans,
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 3,
                    padding: "1px 4px",
                  }}
                >
                  required
                </span>
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                Script that builds your runtime environment. The script is responsible for exporting
                the runtime to the file specified in "Expected output" below.
              </div>
              <FilePicker
                disabled={false}
                value={ree.build_runtime_script}
                onChange={(v) => onReeChange?.({ ...ree, build_runtime_script: v })}
                files={files || MOCK_FILES}
                placeholder="build_runtime.sh"
                filterFn={(p) => /\.sh$/i.test(p)}
              />
            </div>

            {!ree.build_runtime_script && (
              <div
                style={{
                  marginTop: 12,
                  padding: "9px 12px",
                  borderRadius: 7,
                  background: "#ecfeff",
                  border: "1px solid #a5f3fc",
                  color: "#0e7490",
                  fontSize: 11,
                  fontFamily: F.sans,
                  lineHeight: 1.4,
                }}
              >
                No build script yet? Use a predefined default script in the editor below (Docker,
                Nix, Conda, Python venv).
              </div>
            )}

            <div style={{ marginTop: 14 }}>
              <div style={{ ...S_SECTION_LABEL, marginBottom: 10 }}>Build Script Editor</div>
              {SVC_SCRIPT_FIELDS[svc.key]?.map((sf) => (
                <ScriptPanel
                  key={sf.fieldKey}
                  scriptKind={sf.scriptKind || null}
                  fieldKey={sf.fieldKey}
                  files={files || MOCK_FILES}
                  onFilesChange={onFilesChange}
                  ree={ree}
                  onReeChange={onReeChange}
                  onTemplateSuggestedOutput={(out) => setExpectedOutput(out)}
                  saveToWorkspaceOnly
                />
              ))}
            </div>
          </div>

          {/* EXPECTED OUTPUT — Second step in workflow */}
          <div
            style={{
              padding: "20px 24px 16px",
              flexShrink: 0,
              borderBottom: `1px solid ${C.border}`,
              ...tipTargetSectionStyle(focusedField === "runtime"),
            }}
            onClick={() => setFocusedField("runtime")}
            onMouseEnter={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={S_SECTION_LABEL}>Step 2: Expected Output</div>
              {tipTargetChip(focusedField === "runtime")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{ fontSize: 12, fontWeight: 600, color: C.textMid, fontFamily: F.sans }}
                >
                  Exported runtime file path
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: "#ef4444",
                    fontWeight: 700,
                    fontFamily: F.sans,
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 3,
                    padding: "1px 4px",
                  }}
                >
                  required
                </span>
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                The filepath where your build script will export the runtime (e.g.,{" "}
                <code style={{ fontFamily: F.mono, fontSize: 10 }}>runtime.tar.gz</code>).
              </div>
              <input
                value={expectedOutput}
                onChange={(e) => setExpectedOutput(e.target.value)}
                onFocus={() => setFocusedField("runtime")}
                placeholder="runtime.tar.gz"
                style={{
                  border: `1.5px solid ${expectedOutput ? C.accentBorder : C.border}`,
                  borderRadius: 6,
                  padding: "5px 8px",
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.text,
                  background: C.surface,
                  width: "100%",
                  boxSizing: "border-box",
                }}
              />
            </div>

            {/* Additional parameters */}
            {svc.params && svc.params.length > 0 && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                <div style={{ ...S_SECTION_LABEL, marginBottom: 12 }}>Additional Parameters</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}>
                  {svc.params.map((p) => (
                    <div
                      key={p.key}
                      style={{ display: "flex", flexDirection: "column", gap: 5, flex: "0 1 auto" }}
                    >
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: C.textMid,
                          fontFamily: F.sans,
                        }}
                      >
                        {p.label}
                      </div>
                      {p.hint && (
                        <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                          {p.hint}
                        </div>
                      )}
                      {p.type === "bool" ? (
                        <button
                          type="button"
                          onClick={() => setParam(p.key, !params[p.key])}
                          style={{
                            width: 34,
                            height: 19,
                            borderRadius: 99,
                            border: "none",
                            cursor: "pointer",
                            background: params[p.key] ? buildColor : C.borderMid,
                            transition: "background 0.2s",
                            position: "relative",
                          }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              top: 2,
                              left: params[p.key] ? 17 : 2,
                              width: 15,
                              height: 15,
                              borderRadius: "50%",
                              background: "#fff",
                              transition: "left 0.2s",
                              boxShadow: "0 1px 3px rgba(0,0,0,0.18)",
                            }}
                          />
                        </button>
                      ) : p.type === "select" ? (
                        <select
                          value={String(params[p.key] ?? "")}
                          onChange={(e) => setParam(p.key, e.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 6,
                            padding: "5px 8px",
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                          }}
                        >
                          {p.options.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          value={String(params[p.key] ?? "")}
                          onChange={(e) => setParam(p.key, e.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 6,
                            padding: "5px 8px",
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                            boxSizing: "border-box",
                          }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* EXECUTION */}
          <ServiceActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing.length > 0}
            idleLabel="Run build"
            runningLabel="Building…"
            doneLabel="Re-build"
            helperText="Execute the build script and record build logs."
            onRun={() => onRun(svc.key, { ...params, _expectedOutput: expectedOutput })}
          />

          {/* BUILD OUTPUT VERIFICATION — Step 3 in workflow */}
          <div
            style={{ padding: "16px 24px", borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}
          >
            <div style={{ ...S_SECTION_LABEL, marginBottom: 12 }}>Step 3: Verify Build Output</div>
            <RuntimeOutputNode
              expectedOutput={expectedOutput}
              buildDone={runDone}
              ree={ree}
              imageColor={imageColor}
              files={files || MOCK_FILES}
            />
          </div>

          {/* MANUAL OVERRIDE — Optional (hidden behind explicit toggle) */}
          {!showManualOverride ? (
            <div
              style={{ padding: "16px 24px", borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}
            >
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => setShowManualOverride(true)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "9px 14px",
                    borderRadius: 9,
                    border: "1.5px solid #fdba74",
                    background: "#fff7ed",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#9a3412",
                    boxShadow: "0 1px 2px rgba(154,52,18,0.14)",
                    transition: "all 0.14s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "#ffedd5";
                    e.currentTarget.style.borderColor = "#fb923c";
                    e.currentTarget.style.boxShadow = "0 2px 8px rgba(154,52,18,0.18)";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "#fff7ed";
                    e.currentTarget.style.borderColor = "#fdba74";
                    e.currentTarget.style.boxShadow = "0 1px 2px rgba(154,52,18,0.14)";
                    e.currentTarget.style.transform = "translateY(0)";
                  }}
                >
                  <span
                    style={{
                      display: "flex",
                      width: 18,
                      height: 18,
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 5,
                      background: "#fed7aa",
                      color: "#9a3412",
                    }}
                  >
                    {Ic.x(12)}
                  </span>
                  Skip building the runtime and manually set it instead. Not Recommended, please try
                  to make it work using a build script and running the build.
                </button>
                <div style={{ fontSize: 11, color: C.textMuted }}>
                  Only do this if for some reason you cannot build the runtime automatically.
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{ padding: "16px 24px", borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}
            >
              <div style={{ ...S_SECTION_LABEL, marginBottom: 12 }}>Manual Override</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                  You chose to skip building — set the runtime field manually. This will override
                  any automatic detection.
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    background: metaRuntime ? "#f0fdf4" : C.surfaceAlt,
                    border: `1.5px solid ${metaRuntime ? "#bbf7d0" : C.border}`,
                    borderRadius: 8,
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 7,
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: metaRuntime ? "#dcfce7" : `${C.border}40`,
                    }}
                  >
                    <span style={{ color: metaRuntime ? "#16a34a" : C.textMuted, display: "flex" }}>
                      {Ic.files(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: 0.8,
                        fontFamily: F.sans,
                        textTransform: "uppercase",
                        color: metaRuntime ? "#16a34a" : C.textMuted,
                        opacity: 0.7,
                        marginBottom: 1,
                      }}
                    >
                      ree.runtime
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: F.mono,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: metaRuntime ? "#15803d" : C.textMuted,
                      }}
                    >
                      {metaRuntime || (
                        <span style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11 }}>
                          not set
                        </span>
                      )}
                    </div>
                  </div>
                  {metaRuntime && (
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        fontWeight: 700,
                        color: "#16a34a",
                        background: "#f0fdf4",
                        border: "1px solid #bbf7d0",
                        borderRadius: 4,
                        padding: "2px 7px",
                        flexShrink: 0,
                      }}
                    >
                      SET
                    </span>
                  )}
                </div>
                <RuntimeField
                  locked={false}
                  ree={ree}
                  onChange={onReeChange}
                  onFocus={() => setFocusedField("runtime")}
                  active={false}
                  usedBy={[]}
                  files={files || MOCK_FILES}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => setShowManualOverride(false)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "7px 11px",
                      borderRadius: 7,
                      border: `1.5px solid ${C.borderMid}`,
                      background: C.surfaceAlt,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 700,
                      color: C.textMid,
                      transition: "all 0.14s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = C.surface;
                      e.currentTarget.style.borderColor = C.accentBorder;
                      e.currentTarget.style.color = C.accent;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = C.surfaceAlt;
                      e.currentTarget.style.borderColor = C.borderMid;
                      e.currentTarget.style.color = C.textMid;
                    }}
                  >
                    {Ic.arrowLeft(12)} Back to build flow
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* FINAL RUNTIME FIELD — Step 4 */}
          <div
            style={{
              padding: "16px 24px",
              borderBottom: `1px solid ${C.border}`,
              flexShrink: 0,
              ...tipTargetSectionStyle(focusedField === "runtime"),
            }}
            onClick={() => setFocusedField("runtime")}
            onMouseEnter={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = `${C.accentBg}45`;
              e.currentTarget.style.borderLeftColor = C.accentBorder;
            }}
            onMouseLeave={(e) => {
              if (focusedField === "runtime") return;
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderLeftColor = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <div style={S_SECTION_LABEL}>Step 4: Final Runtime Field</div>
              {tipTargetChip(focusedField === "runtime")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  background: finalRuntime ? "#f0fdf4" : C.surfaceAlt,
                  border: `1.5px solid ${finalRuntime ? "#bbf7d0" : C.border}`,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 7,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: finalRuntime ? "#dcfce7" : `${C.border}40`,
                  }}
                >
                  <span style={{ color: finalRuntime ? "#16a34a" : C.textMuted, display: "flex" }}>
                    {Ic.archive(14)}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: 0.8,
                      fontFamily: F.sans,
                      textTransform: "uppercase",
                      color: finalRuntime ? "#16a34a" : C.textMuted,
                      opacity: 0.7,
                      marginBottom: 1,
                    }}
                  >
                    ree.runtime
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      fontFamily: F.mono,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: finalRuntime ? "#15803d" : C.textMuted,
                    }}
                  >
                    {finalRuntime || (
                      <span style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11 }}>
                        not set yet — run build or set manually
                      </span>
                    )}
                  </div>
                </div>
                {finalRuntimeSize && (
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.mono,
                      fontWeight: 700,
                      color: finalRuntime ? "#166534" : C.textMuted,
                      background: finalRuntime ? "#dcfce7" : C.surfaceAlt,
                      border: `1px solid ${finalRuntime ? "#86efac" : C.border}`,
                      borderRadius: 4,
                      padding: "2px 7px",
                      flexShrink: 0,
                    }}
                  >
                    {finalRuntimeSize}
                  </span>
                )}
                {finalRuntime && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginLeft: 4,
                      paddingLeft: 8,
                      borderLeft: `1px solid ${finalRuntime ? "#bbf7d0" : C.border}`,
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                      <div
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: 0.7,
                          textTransform: "uppercase",
                          color: includeRuntime ? "#164e63" : C.textMuted,
                          fontFamily: F.sans,
                        }}
                      >
                        Included
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: includeRuntime ? "#0891b2" : C.textMuted,
                          fontFamily: F.sans,
                        }}
                      >
                        {includeRuntime ? "Yes" : "No"}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onReeChange?.({ ...ree, _runtimeIncluded: !includeRuntime })}
                      style={{
                        width: 34,
                        height: 20,
                        borderRadius: 99,
                        border: "none",
                        cursor: "pointer",
                        background: includeRuntime ? "#06b6d4" : C.borderMid,
                        transition: "background 0.2s",
                        position: "relative",
                        flexShrink: 0,
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: 2,
                          left: includeRuntime ? 16 : 2,
                          width: 16,
                          height: 16,
                          borderRadius: "50%",
                          background: "#fff",
                          transition: "left 0.2s",
                          boxShadow: "0 1px 3px rgba(0,0,0,0.22)",
                        }}
                      />
                    </button>
                  </div>
                )}
                {finalRuntime && (
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      fontWeight: 700,
                      color: "#16a34a",
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: 4,
                      padding: "2px 7px",
                      flexShrink: 0,
                    }}
                  >
                    FINAL
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>
                {finalRuntime
                  ? includeRuntime
                    ? "Runtime will be bundled in the REE archive."
                    : "Runtime will not be bundled in the REE archive."
                  : "Set a runtime value first."}
              </div>
            </div>
          </div>

          {/* Log */}
          <div
            style={{
              padding: "4px 24px 24px",
              flex: 1,
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
            }}
          >
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
          </div>

          {/* Next step nudge */}
          <div style={{ padding: "0 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={svc.key} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["build_runtime_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
          generalTips={[
            "Produce a reproducible runtime artifact from source and scripts.",
            "Keep build outputs deterministic so later SBOM and activation checks are reliable.",
          ]}
        />
      </div>
    </div>
  );
}

const SERVICE_PAGE_COMPONENTS: Record<string, (props: ServicePageProps) => JSX.Element> = {
  evaluate: PageEvaluate,
  build: PageBuildRuntime,
  sbom: PageGenerateSBOM,
  activation: PageTestActivation,
};

// ══════════════════════════════════════════════════════════════════════════════
// PAGE: ARCHIVE (Deposit & Share)
// ══════════════════════════════════════════════════════════════════════════════
interface PageArchiveProps {
  ree: Ree;
  badges: Badges;
  logs: ServiceLogs;
  actionStates: ActionStates;
  onRun: (key: string, params: Record<string, unknown>) => void;
  onGo: (key: string) => void;
}
function PageArchive({ ree, badges, logs, actionStates, onRun, onGo }: PageArchiveProps) {
  const [activeRepo, setActiveRepo] = useState("swh");
  const repo = ARCHIVE_REPOS.find((r) => r.key === activeRepo) || ARCHIVE_REPOS[0];
  const earned = !!badges[activeRepo];
  const running = actionStates[activeRepo] === "loading";
  const log = logs[activeRepo];
  const [params, setParams] = useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(
      ARCHIVE_REPOS.flatMap((r) => r.params.map((p) => [`${r.key}_${p.key}`, p.default])),
    ),
  );
  const getParam = (repoKey: string, paramKey: string): string | boolean =>
    params[`${repoKey}_${paramKey}`];
  const setParam = (repoKey: string, paramKey: string, val: string | boolean) =>
    setParams((p) => ({ ...p, [`${repoKey}_${paramKey}`]: val }));

  const missing = repo.requires.filter((r) => !ree[r.field]);
  const canRun = missing.length === 0 && !running;

  // ID assigned after archival
  const assignedId = ree[repo.idField] as string | undefined;

  const buildDone = !!badges["build"];
  const sbomDone = !!badges["sbom"];
  const activationDone = !!badges["activation"];
  const capstoneReady = buildDone && sbomDone && activationDone;

  return (
    <div style={{ padding: 24, maxWidth: 860, animation: "fadeUp 0.2s ease" }}>
      <div style={{ marginBottom: 22 }}>
        <h2
          style={{
            fontSize: 21,
            fontWeight: 700,
            color: C.text,
            letterSpacing: -0.4,
            marginBottom: 4,
          }}
        >
          Deposit & Share
        </h2>
        <p style={{ fontSize: 13, color: C.textMuted }}>
          Deposit your REE to a long-term research archive to obtain a citable, permanent
          identifier.
        </p>
      </div>

      {/* Capstone gate — warn if upstream steps are incomplete */}
      {!capstoneReady && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "12px 16px",
            marginBottom: 20,
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 10,
          }}
        >
          <span style={{ color: "#b45309", display: "flex", flexShrink: 0, marginTop: 1 }}>
            {Ic.info()}
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#92400e", marginBottom: 4 }}>
              Complete earlier steps before depositing
            </div>
            <div style={{ fontSize: 13, color: "#92400e", lineHeight: 1.5, marginBottom: 8 }}>
              Archiving before building and validating risks depositing an environment that can't be
              reproduced. Complete these steps first:
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {!buildDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ Build Runtime not run
                </span>
              )}
              {!sbomDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ SBOM not generated
                </span>
              )}
              {!activationDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ Activation test not run
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Repo selector tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {ARCHIVE_REPOS.map((r) => {
          const isActive = activeRepo === r.key;
          const isDone = !!badges[r.key];
          return (
            <button
              type="button"
              key={r.key}
              onClick={() => setActiveRepo(r.key)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 16px",
                borderRadius: 8,
                border: `1.5px solid ${isActive ? r.color : isDone ? `${r.color}40` : C.border}`,
                background: isActive ? `${r.color}10` : isDone ? r.bg : C.surface,
                cursor: "pointer",
                transition: "all 0.15s",
                flex: 1,
                justifyContent: "center",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = `${r.color}70`;
                  e.currentTarget.style.background = r.bg;
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = isDone ? `${r.color}40` : C.border;
                  e.currentTarget.style.background = isDone ? r.bg : C.surface;
                }
              }}
            >
              {isDone && <span style={{ color: r.color, display: "flex" }}>{Ic.check(13)}</span>}
              <span
                style={{
                  fontSize: 13,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? r.color : isDone ? r.color : C.textMid,
                  fontFamily: F.sans,
                }}
              >
                {r.label}
              </span>
            </button>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Left: repo info + params */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Repo card */}
          <div
            style={{
              background: C.surface,
              border: `1.5px solid ${repo.border}`,
              borderRadius: 10,
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            }}
          >
            <div
              style={{
                padding: "10px 16px",
                background: repo.bg,
                borderBottom: `1px solid ${repo.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 3,
                  height: 16,
                  borderRadius: 99,
                  background: repo.color,
                  flexShrink: 0,
                }}
              />
              <span
                style={{ fontSize: 14, fontWeight: 700, color: repo.color, fontFamily: F.sans }}
              >
                {repo.label}
              </span>
              <a
                href={repo.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  marginLeft: "auto",
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: repo.color,
                  opacity: 0.7,
                  textDecoration: "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 3,
                }}
              >
                {Ic.link(10)} {repo.url.replace("https://", "")}
              </a>
            </div>
            <div style={{ padding: "12px 16px" }}>
              <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, margin: "0 0 12px" }}>
                {repo.desc}
              </p>
              {/* Assigned ID */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "7px 10px",
                  borderRadius: 7,
                  background: assignedId ? repo.bg : C.surfaceAlt,
                  border: `1px solid ${assignedId ? repo.border : C.border}`,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    color: assignedId ? repo.color : C.textMuted,
                    flexShrink: 0,
                  }}
                >
                  {repo.idLabel}
                </span>
                <span
                  style={{
                    fontSize: 13,
                    fontFamily: F.mono,
                    color: assignedId ? repo.color : C.textMuted,
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {assignedId || repo.idPlaceholder}
                </span>
                {assignedId && (
                  <span
                    style={{
                      fontSize: 11,
                      color: repo.color,
                      background: repo.bg,
                      border: `1px solid ${repo.border}`,
                      borderRadius: 3,
                      padding: "1px 5px",
                      fontFamily: F.mono,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    ✓ assigned
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Parameters */}
          <div
            style={{
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 10,
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            }}
          >
            <div
              style={{
                padding: "8px 16px",
                background: "#fafbfd",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 3,
                  height: 14,
                  borderRadius: 99,
                  background: C.borderMid,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: 1,
                  color: C.textMuted,
                  textTransform: "uppercase",
                  fontFamily: F.sans,
                }}
              >
                Parameters
              </span>
            </div>
            <div
              style={{ padding: "10px 16px", display: "flex", flexDirection: "column", gap: 10 }}
            >
              {repo.params.map((p) => (
                <div key={p.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                    <label
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: C.textMid,
                        fontFamily: F.sans,
                      }}
                    >
                      {p.label}
                    </label>
                    <span style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</span>
                  </div>
                  {p.type === "bool" ? (
                    <button
                      type="button"
                      onClick={() => setParam(repo.key, p.key, !getParam(repo.key, p.key))}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 7,
                        padding: "6px 10px",
                        borderRadius: 6,
                        border: `1.5px solid ${getParam(repo.key, p.key) ? C.accent : C.border}`,
                        background: getParam(repo.key, p.key) ? C.accentBg : C.bg,
                        cursor: "pointer",
                        width: "fit-content",
                        transition: "all 0.15s",
                      }}
                    >
                      <div
                        style={{
                          width: 30,
                          height: 16,
                          borderRadius: 99,
                          background: getParam(repo.key, p.key) ? C.accent : C.borderMid,
                          position: "relative",
                          transition: "background 0.2s",
                        }}
                      >
                        <div
                          style={{
                            position: "absolute",
                            top: 2,
                            left: getParam(repo.key, p.key) ? 16 : 2,
                            width: 12,
                            height: 12,
                            borderRadius: "50%",
                            background: "#fff",
                            transition: "left 0.2s",
                          }}
                        />
                      </div>
                      <span
                        style={{
                          fontSize: 13,
                          fontFamily: F.sans,
                          color: getParam(repo.key, p.key) ? C.accent : C.textMuted,
                        }}
                      >
                        {getParam(repo.key, p.key) ? "yes" : "no"}
                      </span>
                    </button>
                  ) : p.type === "select" ? (
                    <select
                      value={String(getParam(repo.key, p.key) ?? "")}
                      onChange={(e) => setParam(repo.key, p.key, e.target.value)}
                      style={{
                        border: `1.5px solid ${C.border}`,
                        borderRadius: 7,
                        padding: "6px 10px",
                        fontSize: 14,
                        fontFamily: F.mono,
                        color: C.text,
                        background: C.surface,
                      }}
                    >
                      {p.options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={String(getParam(repo.key, p.key) ?? "")}
                      onChange={(e) => setParam(repo.key, p.key, e.target.value)}
                      style={{
                        border: `1.5px solid ${C.border}`,
                        borderRadius: 7,
                        padding: "6px 10px",
                        fontSize: 14,
                        fontFamily: F.mono,
                        color: C.text,
                        background: C.surface,
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Missing requirements warning */}
          {missing.length > 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                padding: "10px 13px",
                background: "#fef3c7",
                border: "1px solid #fde68a",
                borderRadius: 8,
              }}
            >
              <span style={{ color: "#92400e", flexShrink: 0, marginTop: 1 }}>{Ic.info(13)}</span>
              <div style={{ fontSize: 13, color: "#92400e", lineHeight: 1.5 }}>
                <strong>Missing required fields:</strong> {missing.map((r) => r.label).join(", ")}
              </div>
            </div>
          )}

          {/* Deposit button */}
          <button
            type="button"
            onClick={() =>
              canRun &&
              onRun(
                repo.key,
                Object.fromEntries(repo.params.map((p) => [p.key, getParam(repo.key, p.key)])),
              )
            }
            disabled={!canRun}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "11px",
              borderRadius: 9,
              background: !canRun ? C.surfaceAlt : earned ? repo.bg : repo.color,
              border: earned ? `1.5px solid ${repo.border}` : "none",
              color: !canRun ? C.textMuted : earned ? repo.color : "#fff",
              fontSize: 15,
              fontWeight: 700,
              fontFamily: F.sans,
              cursor: canRun ? "pointer" : "default",
              boxShadow: canRun && !earned ? `0 2px 12px ${repo.color}40` : "none",
              transition: "all 0.2s",
            }}
          >
            <span
              style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
            >
              {running ? Ic.loader(15) : earned ? Ic.check(15) : Ic.upload(15)}
            </span>
            {running
              ? `Depositing to ${repo.label}…`
              : earned
                ? `Re-deposit to ${repo.label}`
                : `Deposit to ${repo.label}`}
          </button>
        </div>

        {/* Right: log output */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: 1.3,
              color: C.textMuted,
              fontFamily: F.sans,
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            Output
          </div>
          <LogPanel log={log} running={running} />
        </div>
      </div>

      {/* Next step nudge */}
      <div style={{ padding: "24px 24px 24px", flexShrink: 0 }}>
        <NextStepNudge stepKey={PAGE.ARCHIVE} badges={badges || {}} onGo={onGo} />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE: FILES — two-pane file browser: workspace | REE files
// ══════════════════════════════════════════════════════════════════════════════

// Flatten a file tree into a list of file nodes (no folders)
function flattenTree(nodes: FileTreeNode[]): FileTreeNode[] {
  const result = [];
  for (const node of nodes || []) {
    if (node.type === "folder") result.push(...flattenTree(node.children));
    else result.push(node);
  }
  return result;
}

function buildReeFileTree(reeFiles: ReeFile[]): FileTreeNode[] {
  const roots: FileTreeNode[] = [];

  function ensureFolder(
    nodes: FileTreeNode[],
    folderName: string,
    folderPath: string,
  ): FileTreeNode {
    const existing = nodes.find((n) => n.type === "folder" && n.name === folderName);
    if (existing) return existing;
    const created: FileTreeNode = {
      id: `ree-dir-${folderPath}`,
      name: folderName,
      type: "folder",
      children: [],
    };
    nodes.push(created);
    return created;
  }

  for (const file of reeFiles || []) {
    const parts = file.name.split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let cursor = roots;
    let folderPath = "";
    for (let idx = 0; idx < parts.length - 1; idx++) {
      const part = parts[idx];
      folderPath = folderPath ? `${folderPath}/${part}` : part;
      const folder = ensureFolder(cursor, part, folderPath);
      cursor = folder.children || [];
      folder.children = cursor;
    }

    const fileName = parts[parts.length - 1];
    const existingFileIdx = cursor.findIndex((n) => n.type === "file" && n.name === fileName);
    const fileNode: FileTreeNode = {
      id: file.id,
      name: fileName,
      type: "file",
      content: file.content,
      tag: file.tag,
    };
    if (existingFileIdx >= 0) cursor[existingFileIdx] = fileNode;
    else cursor.push(fileNode);
  }

  return roots;
}

// Shared syntax-highlighted file viewer panel
interface FileViewerProps {
  file: FileTreeNode | ReeFile;
  onClose: () => void;
  label?: string;
}
function FileViewer({ file, onClose, label }: FileViewerProps) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(file.content || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const lines = (file.content || "").split("\n");

  return (
    <div
      style={{ display: "flex", flexDirection: "column", height: "100%", background: "#f8fafc" }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: `1px solid ${C.border}`,
          background: C.surface,
          flexShrink: 0,
        }}
      >
        <span style={{ display: "flex", color: C.textMuted }}>{Ic.file(12)}</span>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 12,
            color: C.textMid,
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {file.name}
        </span>
        {label && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: 0.5,
              color: C.textMuted,
              background: C.surfaceAlt,
              border: `1px solid ${C.border}`,
              borderRadius: 3,
              padding: "1px 5px",
              fontFamily: F.sans,
              flexShrink: 0,
            }}
          >
            {label}
          </span>
        )}
        <button
          type="button"
          onClick={copy}
          style={{
            background: "none",
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            cursor: "pointer",
            padding: "2px 8px",
            fontSize: 10,
            fontFamily: F.sans,
            color: copied ? "#16a34a" : C.textMuted,
            transition: "all 0.12s",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            if (!copied) {
              e.currentTarget.style.borderColor = C.accent;
              e.currentTarget.style.color = C.accent;
            }
          }}
          onMouseLeave={(e) => {
            if (!copied) {
              e.currentTarget.style.borderColor = C.border;
              e.currentTarget.style.color = C.textMuted;
            }
          }}
        >
          {copied ? "✓ copied" : "copy"}
        </button>
        <button
          type="button"
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: C.textMuted,
            display: "flex",
            padding: 2,
            borderRadius: 4,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = C.text)}
          onMouseLeave={(e) => (e.currentTarget.style.color = C.textMuted)}
        >
          {Ic.x(12)}
        </button>
      </div>
      {/* Lines */}
      <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
        {lines.map((line, i) => (
          <div key={i} style={{ display: "flex", alignItems: "baseline" }}>
            <span
              style={{
                minWidth: 40,
                textAlign: "right",
                paddingRight: 14,
                paddingLeft: 10,
                fontSize: 10,
                fontFamily: F.mono,
                color: C.borderMid,
                userSelect: "none",
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            <span
              style={{
                fontSize: 12,
                fontFamily: F.mono,
                lineHeight: 1.75,
                whiteSpace: "pre",
                display: "block",
                paddingRight: 16,
                color: line.startsWith("#")
                  ? "#94a3b8"
                  : /^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)
                    ? "#0369a1"
                    : /^(set |echo |docker |pip )/.test(line)
                      ? "#15803d"
                      : /^\s*"/.test(line) && line.includes(":")
                        ? "#b45309"
                        : C.text,
              }}
            >
              {line || " "}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface PageFilesProps {
  files: FileTreeNode[];
  reeFiles: ReeFile[];
}
function PageFiles({ files, reeFiles }: PageFilesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sourceFiles = files || MOCK_FILES;
  const reeFileTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const reeFlatFiles = useMemo(() => flattenTree(reeFileTree), [reeFileTree]);

  // Always derive displayed file from current lists so manifest stays live
  const allFiles = [...flattenTree(sourceFiles), ...reeFlatFiles];
  const selectedFile = selectedId ? allFiles.find((f) => f.id === selectedId) || null : null;

  const SectionHeader = ({ label, badge, color }) => (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "7px 10px 5px",
        position: "sticky",
        top: 0,
        background: C.surface,
        zIndex: 1,
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <div style={{ width: 3, height: 12, borderRadius: 99, background: color, flexShrink: 0 }} />
      <span
        style={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 1.3,
          color: C.textMid,
          textTransform: "uppercase",
          fontFamily: F.sans,
          flex: 1,
        }}
      >
        {label}
      </span>
      {badge && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: C.textMuted,
            background: C.surfaceAlt,
            border: `1px solid ${C.border}`,
            borderRadius: 3,
            padding: "1px 5px",
            fontFamily: F.sans,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", animation: "fadeUp 0.2s ease" }}>
      {/* Single tree pane */}
      <div
        style={{
          width: selectedFile ? 200 : 280,
          borderRight: `1px solid ${C.border}`,
          background: C.surface,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          flexShrink: 0,
          transition: "width 0.18s",
        }}
      >
        <div style={{ overflowY: "auto", flex: 1 }}>
          {/* Workspace section */}
          <SectionHeader label="Workspace" badge="read-only" color="#f59e0b" />
          <div style={{ padding: "4px 4px 8px" }}>
            {sourceFiles.map((n) => (
              <FileNode
                key={n.id}
                node={n}
                onSelect={(n) => setSelectedId(n.id)}
                selectedId={selectedId}
              />
            ))}
          </div>

          {/* REE section */}
          <SectionHeader
            label="REE Files"
            badge={`${reeFiles.length} file${reeFiles.length !== 1 ? "s" : ""}`}
            color="#7c3aed"
          />
          <div style={{ padding: "4px 4px 8px" }}>
            {reeFiles.length === 0 ? (
              <div
                style={{
                  padding: "10px 12px",
                  fontSize: 11,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  fontStyle: "italic",
                }}
              >
                Run Create &amp; Build to generate files
              </div>
            ) : (
              reeFileTree.map((n) => (
                <FileNode
                  key={n.id}
                  node={n}
                  onSelect={(n) => setSelectedId(n.id)}
                  selectedId={selectedId}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Viewer */}
      {selectedFile ? (
        <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
          <FileViewer
            file={selectedFile}
            onClose={() => setSelectedId(null)}
            label={reeFlatFiles.find((f) => f.id === selectedId) ? "ree" : "workspace"}
          />
        </div>
      ) : (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: C.textMuted,
            flexDirection: "column",
            gap: 8,
            background: "#f8fafc",
          }}
        >
          <span style={{ display: "flex", opacity: 0.3 }}>{Ic.file(28)}</span>
          <span style={{ fontSize: 13, fontFamily: F.sans }}>Select a file to view</span>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// OVERVIEW — pod visualisation page
// ══════════════════════════════════════════════════════════════════════════════

// Purely decorative cables — fill the ring visually, no semantic meaning.
// Placed in the gaps between the 4 real anchors at intermediate angles.
// Distances are pushed well past the SVG boundary (580×580, centre 290,290)
// so the cables trail off-screen rather than terminating in mid-air.
interface DecoAnchor {
  id: string;
  angle: number;
  dist: number;
}
const DECO_ANCHORS: DecoAnchor[] = [
  { id: "d1", angle: -135, dist: 380 }, // upper-left → off top-left corner
  { id: "d2", angle: -45, dist: 370 }, // upper-right → off top-right corner
  { id: "d3", angle: 22, dist: 340 }, // right-ish, slightly up → off right edge
  { id: "d4", angle: 68, dist: 355 }, // right-ish, slightly down → off right edge
  { id: "d5", angle: 112, dist: 345 }, // lower-right → off bottom-right
  { id: "d6", angle: 158, dist: 360 }, // lower-left → off bottom-left
  { id: "d7", angle: 202, dist: 375 }, // left-ish, slightly down → off left edge
  { id: "d8", angle: 248, dist: 350 }, // lower-left-ish → off bottom-left
  { id: "d9", angle: 292, dist: 365 }, // left-ish, slightly up → off left edge
  { id: "d10", angle: 337, dist: 355 }, // upper-left-ish → off top edge
];

const POD_M: Record<string, string> = {
  face: "#e8edf4",
  raised: "#f2f5f9",
  shadow: "#c8d0dc",
  deep: "#a8b4c4",
  bolt: "#cdd5e0",
  boltC: "#9aa5b4",
  weld: "#b8c4d4",
};

interface PodBoltProps {
  cx: number;
  cy: number;
  r?: number;
}
function PodBolt({ cx, cy, r = 5 }: PodBoltProps) {
  const pts = Array.from({ length: 6 })
    .map((_, i) => {
      const a = (i / 6) * Math.PI * 2 - Math.PI / 6;
      return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    })
    .join(" ");
  return (
    <g>
      <polygon points={pts} fill={POD_M.bolt} stroke={POD_M.deep} strokeWidth="0.7" />
      <circle cx={cx} cy={cy} r={r * 0.38} fill={POD_M.boltC} />
      <polygon
        points={pts}
        fill="none"
        stroke={POD_M.raised}
        strokeWidth="0.4"
        opacity="0.8"
        transform="translate(-0.4,-0.4)"
      />
    </g>
  );
}
interface PodBoltRingProps {
  cx: number;
  cy: number;
  r: number;
  n?: number;
  bR?: number;
}
function PodBoltRing({ cx, cy, r, n = 8, bR = 4.5 }: PodBoltRingProps) {
  return Array.from({ length: n }).map((_, i) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    return <PodBolt key={i} cx={cx + r * Math.cos(a)} cy={cy + r * Math.sin(a)} r={bR} />;
  });
}

interface PodGraphNode {
  x: number;
  y: number;
  r: number;
  root?: boolean;
}
interface PodGraph {
  nodes: PodGraphNode[];
  edges: [number, number][];
}
const POD_GRAPHS: (PodGraph | null)[] = [
  null,
  { nodes: [{ x: 0, y: 0, r: 7, root: true }], edges: [] },
  {
    nodes: [
      { x: 0, y: -20, r: 7, root: true },
      { x: -17, y: 13, r: 5 },
      { x: 17, y: 13, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
    ],
  },
  {
    nodes: [
      { x: 0, y: -24, r: 7, root: true },
      { x: -21, y: 0, r: 5 },
      { x: 21, y: 0, r: 5 },
      { x: -12, y: 21, r: 4 },
      { x: 12, y: 21, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -26, r: 7, root: true },
      { x: -23, y: -7, r: 5 },
      { x: 23, y: -7, r: 5 },
      { x: -26, y: 13, r: 4 },
      { x: 0, y: 19, r: 5 },
      { x: 26, y: 13, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 5],
      [1, 4],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -28, r: 7, root: true },
      { x: -24, y: -11, r: 5 },
      { x: 24, y: -11, r: 5 },
      { x: -30, y: 7, r: 4 },
      { x: -10, y: 15, r: 4 },
      { x: 10, y: 15, r: 4 },
      { x: 30, y: 7, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 4],
      [5, 6],
    ],
  },
  {
    nodes: [
      { x: 0, y: -30, r: 7, root: true },
      { x: -25, y: -13, r: 5 },
      { x: 25, y: -13, r: 5 },
      { x: -32, y: 4, r: 4 },
      { x: -13, y: 9, r: 4 },
      { x: 13, y: 9, r: 4 },
      { x: 32, y: 4, r: 4 },
      { x: 0, y: 26, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 7],
      [4, 7],
      [5, 7],
    ],
  },
  {
    nodes: [
      { x: 0, y: -32, r: 7, root: true },
      { x: -26, y: -15, r: 5 },
      { x: 26, y: -15, r: 5 },
      { x: -34, y: 2, r: 4 },
      { x: -14, y: 7, r: 4 },
      { x: 14, y: 7, r: 4 },
      { x: 34, y: 2, r: 4 },
      { x: -21, y: 22, r: 4 },
      { x: 0, y: 28, r: 5 },
      { x: 21, y: 22, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 9],
      [4, 8],
      [5, 8],
      [7, 8],
      [8, 9],
      [3, 4],
      [5, 6],
    ],
  },
];

interface PodDepGraphProps {
  level: number;
  lv: Level;
}
function PodDepGraph({ level, lv }: PodDepGraphProps) {
  if (level === 0)
    return (
      <g opacity="0.3">
        <circle
          cx="0"
          cy="0"
          r="7"
          fill="none"
          stroke={POD_M.shadow}
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
      </g>
    );
  const cfg = POD_GRAPHS[level];
  return (
    <g>
      {cfg.edges.map(([a, b], i) => {
        const na = cfg.nodes[a],
          nb = cfg.nodes[b];
        return (
          <line
            key={i}
            x1={na.x}
            y1={na.y}
            x2={nb.x}
            y2={nb.y}
            stroke={lv.color}
            strokeWidth="1.6"
            opacity="0.38"
          />
        );
      })}
      {cfg.nodes.map((n, i) => (
        <g key={i}>
          <circle
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill={n.root ? lv.color : C.surface}
            stroke={lv.color}
            strokeWidth={n.root ? 0 : 1.8}
          />
          {n.root && <circle cx={n.x} cy={n.y} r={n.r * 0.38} fill="#fff" opacity="0.75" />}
        </g>
      ))}
    </g>
  );
}

interface PodSphereProps {
  CX: number;
  CY: number;
  SR: number;
  level: number;
}
function PodSphere({ CX, CY, SR, level }: PodSphereProps) {
  const lv = LEVELS[Math.min(level, 7)],
    frac = level / 7;
  return (
    <g>
      <defs>
        <radialGradient id="ovPodFace" cx="36%" cy="30%" r="70%">
          <stop offset="0%" stopColor={POD_M.raised} />
          <stop offset="55%" stopColor={POD_M.face} />
          <stop offset="100%" stopColor={POD_M.shadow} />
        </radialGradient>
        <radialGradient id="ovPortholeBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={lv.bg} />
          <stop offset="100%" stopColor={lv.bg} stopOpacity="0.55" />
        </radialGradient>
        <radialGradient id="ovPortholeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={lv.color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={lv.color} stopOpacity="0" />
        </radialGradient>
        <radialGradient id="ovPortholeGloss" cx="32%" cy="28%" r="56%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <clipPath id="ovPortholeClip">
          <circle cx={CX} cy={CY} r={SR * 0.46} />
        </clipPath>
      </defs>
      <ellipse
        cx={CX + 5}
        cy={CY + SR * 0.85}
        rx={SR * 0.72}
        ry={SR * 0.14}
        fill="#0d1117"
        opacity="0.08"
      />
      <circle cx={CX} cy={CY} r={SR + 1} fill={POD_M.deep} opacity="0.4" />
      <circle cx={CX} cy={CY} r={SR} fill="url(#ovPodFace)" stroke={POD_M.deep} strokeWidth="1.2" />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR}
        ry={SR * 0.28}
        fill="none"
        stroke={POD_M.weld}
        strokeWidth="0.9"
        opacity="0.7"
      />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR * 0.28}
        ry={SR}
        fill="none"
        stroke={POD_M.weld}
        strokeWidth="0.9"
        opacity="0.5"
      />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR}
        ry={SR * 0.18}
        fill={POD_M.shadow}
        stroke={POD_M.deep}
        strokeWidth="1"
        opacity="0.55"
      />
      {Array.from({ length: 10 }).map((_, i) => {
        const a = (i / 10) * Math.PI * 2;
        return Math.abs(Math.cos(a)) < 0.92 ? (
          <PodBolt
            key={i}
            cx={CX + (SR - 5) * Math.cos(a)}
            cy={CY + SR * 0.13 * Math.sin(a)}
            r={3.8}
          />
        ) : null;
      })}
      <ellipse
        cx={CX}
        cy={CY - SR * 0.72}
        rx={SR * 0.52}
        ry={SR * 0.22}
        fill={POD_M.face}
        stroke={POD_M.weld}
        strokeWidth="0.8"
        opacity="0.8"
      />
      <PodBoltRing cx={CX} cy={CY - SR * 0.72} r={SR * 0.36} n={6} bR={3.5} />
      <ellipse
        cx={CX}
        cy={CY + SR * 0.72}
        rx={SR * 0.52}
        ry={SR * 0.22}
        fill={POD_M.shadow}
        stroke={POD_M.weld}
        strokeWidth="0.8"
        opacity="0.7"
      />
      <PodBoltRing cx={CX} cy={CY + SR * 0.72} r={SR * 0.36} n={6} bR={3.5} />
      <circle
        cx={CX}
        cy={CY}
        r={SR * 0.58}
        fill={POD_M.shadow}
        stroke={POD_M.deep}
        strokeWidth="1.5"
      />
      <PodBoltRing cx={CX} cy={CY} r={SR * 0.53} n={12} bR={3.8} />
      <circle cx={CX} cy={CY} r={SR * 0.48} fill={POD_M.deep} stroke={POD_M.weld} strokeWidth="2" />
      <circle cx={CX} cy={CY} r={SR * 0.46} fill="#050e1a" stroke={POD_M.deep} strokeWidth="1" />
      <circle cx={CX} cy={CY} r={SR * 0.45} fill="url(#ovPortholeBg)" />
      {level > 0 &&
        (() => {
          const r = SR * 0.43,
            ang = frac * 2 * Math.PI,
            x2 = CX + r * Math.sin(ang),
            y2 = CY - r * Math.cos(ang);
          return (
            <path
              d={`M ${CX} ${CY - r} A ${r} ${r} 0 ${frac > 0.5 ? 1 : 0} 1 ${x2} ${y2}`}
              fill="none"
              stroke={lv.color}
              strokeWidth="3.5"
              opacity="0.5"
              strokeLinecap="round"
            />
          );
        })()}
      <circle cx={CX} cy={CY} r={SR * 0.44} fill="url(#ovPortholeGlow)" />
      <g transform={`translate(${CX},${CY})`} clipPath="url(#ovPortholeClip)">
        <PodDepGraph level={level} lv={lv} />
      </g>
      <circle cx={CX} cy={CY} r={SR * 0.45} fill="url(#ovPortholeGloss)" opacity="0.5" />
      <ellipse
        cx={CX - SR * 0.14}
        cy={CY - SR * 0.18}
        rx={SR * 0.16}
        ry={SR * 0.08}
        fill="white"
        opacity="0.32"
        transform={`rotate(-22,${CX - SR * 0.14},${CY - SR * 0.18})`}
      />
      {[
        { a: -55, col: "#16a34a" },
        { a: 55, col: level >= 4 ? "#0ea5e9" : POD_M.shadow },
        { a: 125, col: level >= 7 ? "#059669" : POD_M.shadow },
        { a: 235, col: POD_M.shadow },
      ].map((s, i) => {
        const px = CX + SR * 0.82 * Math.cos((s.a * Math.PI) / 180),
          py = CY + SR * 0.82 * Math.sin((s.a * Math.PI) / 180);
        return (
          <g key={i}>
            <rect
              x={px - 5}
              y={py - 5}
              width="10"
              height="10"
              rx="2"
              fill={POD_M.face}
              stroke={POD_M.deep}
              strokeWidth="0.8"
            />
            <circle cx={px} cy={py} r="3" fill={s.col} opacity="0.9" />
          </g>
        );
      })}
      <rect
        x={CX - 36}
        y={CY + SR - 26}
        width="72"
        height="14"
        rx="2"
        fill={POD_M.face}
        stroke={POD_M.weld}
        strokeWidth="0.8"
      />
      <text
        x={CX}
        y={CY + SR - 16}
        textAnchor="middle"
        fontSize="7"
        fontFamily={F.mono}
        fill={lv.ink}
        letterSpacing="1.5"
      >
        {lv.short}
      </text>
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill="none"
        stroke={lv.color}
        strokeWidth="1.5"
        opacity="0.4"
      />
      <path
        d={`M ${CX - SR * 0.68} ${CY - SR * 0.28} A ${SR} ${SR} 0 0 1 ${CX - SR * 0.28} ${CY - SR * 0.68}`}
        fill="none"
        stroke="white"
        strokeWidth="2"
        opacity="0.3"
        strokeLinecap="round"
      />
    </g>
  );
}

interface PodWidgetProps {
  level: number;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
}
function PodWidget({ level, svgRef, size = 480 }: PodWidgetProps) {
  const lv = LEVELS[Math.min(level, 7)];
  const W = 580,
    H = 580,
    CX = 290,
    CY = 290,
    SR = 118;
  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        flexShrink: 0,
        overflow: "visible",
        filter: `drop-shadow(0 4px 24px ${lv.color}28) drop-shadow(0 2px 8px ${POD_M.shadow})`,
      }}
    >
      <title>Specimen Pod</title>
      <PodSphere CX={CX} CY={CY} SR={SR} level={level} />
    </svg>
  );
}

// ── Panel Cable Overlay ────────────────────────────────────────────────────────
// Cables connecting side panels → specimen pod sphere.
// Uses svg.getScreenCTM() to map the sphere's SVG-space centre (290,290) into
// page pixels, so the endpoints stay glued to the actual rendered sphere no
// matter how the layout reflows or the window resizes.
interface PanelCableOverlayProps {
  containerRef: React.RefObject<HTMLDivElement>;
  sourceRef: React.RefObject<HTMLDivElement>;
  runtimeRef: React.RefObject<HTMLDivElement>;
  metadataRef: React.RefObject<HTMLDivElement>;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  sbomRef: React.RefObject<HTMLDivElement>;
  sealRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  level: number;
  badges: Badges;
  ree: Ree;
}

type PanelCableSide = "left" | "right" | "top";

interface PanelCableSpec {
  id: string;
  ref: React.RefObject<HTMLDivElement>;
  side: PanelCableSide;
  color: string;
  shadow: string;
  connected: boolean;
}

function PanelCableOverlay({
  containerRef,
  sourceRef,
  runtimeRef,
  metadataRef,
  swhRef,
  evaluateRef,
  sbomRef,
  sealRef,
  archiveRef,
  activationRef,
  podSvgRef,
  level,
  badges,
  ree,
}: PanelCableOverlayProps) {
  const lv = LEVELS[Math.min(level, 7)];
  // Store computed geometry as plain state so re-renders are cheap
  const [geo, setGeo] = React.useState<CableGeo | null>(null);
  const rafRef = useRef<number | null>(null);

  // Convert a point (px,py) in the pod SVG's local coordinate system to
  // coordinates relative to the overlay container.
  function svgPtToContainer(
    svg: SVGSVGElement,
    container: HTMLElement,
    px: number,
    py: number,
  ): { x: number; y: number } | null {
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const cRect = container.getBoundingClientRect();
    return {
      x: ctm.a * px + ctm.c * py + ctm.e - cRect.left,
      y: ctm.b * px + ctm.d * py + ctm.f - cRect.top,
    };
  }

  function measure() {
    const container = containerRef.current;
    const podSvg = podSvgRef.current;
    if (!container || !podSvg) return;

    const cRect = container.getBoundingClientRect();

    // Pod sphere centre & radius in pod-SVG local coords (fixed by PodWidget)
    const SVG_CX = 290,
      SVG_CY = 290,
      SVG_SR = 118;

    // Map sphere centre to container-relative coords
    const sphereC = svgPtToContainer(podSvg, container, SVG_CX, SVG_CY);
    if (!sphereC) return;

    // Map a point on the sphere rim to get the rendered radius
    const sphereEdge = svgPtToContainer(podSvg, container, SVG_CX + SVG_SR, SVG_CY);
    if (!sphereEdge) return;
    const sphereR = sphereEdge.x - sphereC.x;

    function panelRel(
      el: HTMLElement | null,
    ): { left: number; right: number; midY: number; midX: number; top: number } | null {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        left: r.left - cRect.left,
        right: r.right - cRect.left,
        midY: (r.top + r.bottom) / 2 - cRect.top,
        midX: (r.left + r.right) / 2 - cRect.left,
        top: r.top - cRect.top,
      };
    }

    // For each cable: panel connector point + sphere surface intercept.
    // The sphere intercept is the point on the sphere rim closest to the
    // panel connector (i.e. on the line from sphere centre → panel).
    function sphereIntercept(panelX: number, panelY: number): { x: number; y: number } {
      const dx = panelX - sphereC.x,
        dy = panelY - sphereC.y;
      const len = Math.hypot(dx, dy) || 1;
      return { x: sphereC.x + (dx / len) * sphereR, y: sphereC.y + (dy / len) * sphereR };
    }

    const fieldsConnected =
      (["name", "origin_url", "runtime", "build_runtime_script"] as (keyof Ree)[]).filter(
        (f) => ree && !!ree[f],
      ).length >= 2;
    const archiveConnected = !!(ree && (ree.zenodo_doi || ree.dataverse_doi));
    const activationConnected = !!(badges && badges["activation"]);
    const sourceConnected = !!(ree && ree._sourceAvailable);
    const runtimeConnected = !!(ree && ree._runtimeIncluded);
    const sbomConnected = !!(ree && ree.sbom && ree.sbom.trim());
    const swhConnected = !!(ree && ree.swhid && ree.swhid.trim());
    const evaluateConnected = !!(badges && badges["evaluate"]);
    const sealConnected = !!(ree && ree._sealedAt);

    const panelSpecs: PanelCableSpec[] = [
      {
        id: PAGE.SOURCE,
        ref: sourceRef,
        side: "right",
        color: "#f59e0b",
        shadow: "#92400e",
        connected: sourceConnected,
      },
      {
        id: "runtime",
        ref: runtimeRef,
        side: "right",
        color: "#0891b2",
        shadow: "#164e63",
        connected: runtimeConnected,
      },
      {
        id: "sbom",
        ref: sbomRef,
        side: "right",
        color: "#16a34a",
        shadow: "#14532d",
        connected: sbomConnected,
      },
      {
        id: "fields",
        ref: metadataRef,
        side: "right",
        color: "#22c55e",
        shadow: "#166534",
        connected: fieldsConnected,
      },
      {
        id: "archive",
        ref: archiveRef,
        side: "left",
        color: "#e4572e",
        shadow: "#7c2d12",
        connected: archiveConnected,
      },
      {
        id: "activation",
        ref: activationRef,
        side: "left",
        color: "#7c3aed",
        shadow: "#3b0764",
        connected: activationConnected,
      },
      {
        id: "swh",
        ref: swhRef,
        side: "left",
        color: "#e4572e",
        shadow: "#7c2d12",
        connected: swhConnected,
      },
      {
        id: "evaluate",
        ref: evaluateRef,
        side: "left",
        color: "#7c3aed",
        shadow: "#3b0764",
        connected: evaluateConnected,
      },
      {
        id: "seal",
        ref: sealRef,
        side: "top",
        color: "#f59e0b",
        shadow: "#78350f",
        connected: sealConnected,
      },
    ];

    const cables: Cable[] = [];
    panelSpecs.forEach((panelSpec) => {
      const panel = panelRel(panelSpec.ref.current);
      if (!panel) return;

      let px = panel.midX;
      let py = panel.midY;
      if (panelSpec.side === "left") px = panel.left;
      if (panelSpec.side === "right") px = panel.right;
      if (panelSpec.side === "top") py = panel.top;

      const pod = sphereIntercept(px, py);
      cables.push({
        id: panelSpec.id,
        x1: px,
        y1: py,
        x2: pod.x,
        y2: pod.y,
        color: panelSpec.color,
        shadow: panelSpec.shadow,
        connected: panelSpec.connected,
      });
    });

    // Decorative cables — computed in pod-SVG space then mapped to container coords.
    // These are rendered first in the overlay SVG so they sit behind everything.
    const SVG_W = 580;
    const decoCables = DECO_ANCHORS.map((anc) => {
      const sa = (anc.angle * Math.PI) / 180;
      // Start: sphere surface in pod-SVG coords
      const startSvg = { x: SVG_CX + SVG_SR * Math.cos(sa), y: SVG_CY + SVG_SR * Math.sin(sa) };
      // End: far endpoint in pod-SVG coords (may be off-screen)
      const endSvg = { x: SVG_CX + anc.dist * Math.cos(sa), y: SVG_CY + anc.dist * Math.sin(sa) };
      const start = svgPtToContainer(podSvg, container, startSvg.x, startSvg.y);
      const end = svgPtToContainer(podSvg, container, endSvg.x, endSvg.y);
      if (!start || !end) return null;
      return { id: anc.id, x1: start.x, y1: start.y, x2: end.x, y2: end.y };
    }).filter(Boolean);

    const w = cRect.width,
      h = cRect.height;
    setGeo({ cables, decoCables, w, h });
  }

  // Re-measure whenever logical state changes (level, badges, ree fields).
  React.useEffect(() => {
    // Schedule via rAF so layout is settled after the state-driven re-render.
    rafRef.current = requestAnimationFrame(measure);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [level, badges, ree]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-measure whenever the container or any observed element is resized.
  React.useEffect(() => {
    const panelRefs = [
      sourceRef,
      runtimeRef,
      metadataRef,
      swhRef,
      evaluateRef,
      sbomRef,
      sealRef,
      archiveRef,
      activationRef,
    ];
    const targets = [containerRef, ...panelRefs] as React.RefObject<Element>[];

    const ro = new ResizeObserver(() => {
      rafRef.current = requestAnimationFrame(measure);
    });

    targets.forEach((r) => {
      if (r.current) ro.observe(r.current);
    });
    return () => ro.disconnect();
  }); // intentionally no dep array — refs may attach/detach between renders

  if (!geo) return null;
  const { cables, decoCables, w, h } = geo;

  function cablePath(x1: number, y1: number, x2: number, y2: number): string {
    // Horizontal cubic bezier with a gentle gravity droop
    const dx = x2 - x1;
    const len = Math.hypot(dx, y2 - y1);
    const droop = len * 0.13;
    const cx1 = x1 + dx * 0.42,
      cy1 = y1 + droop * 0.6;
    const cx2 = x2 - dx * 0.42,
      cy2 = y2 + droop * 0.4;
    return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
  }
  function cableHL(x1: number, y1: number, x2: number, y2: number): string {
    const dx = x2 - x1;
    const len = Math.hypot(dx, y2 - y1);
    const droop = len * 0.13;
    const cy1 = y1 + droop * 0.6 - 1.8;
    const cy2 = y2 + droop * 0.4 - 1.8;
    return `M ${x1} ${y1 - 1.4} C ${x1 + dx * 0.42} ${cy1}, ${x2 - dx * 0.42} ${cy2}, ${x2} ${y2 - 1.4}`;
  }

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "visible",
        zIndex: 0,
      }}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
    >
      <title>Panel connections</title>
      <defs>
        {(decoCables || []).map((dc) => (
          <linearGradient
            key={dc.id}
            id={`oDecoFade_${dc.id}`}
            gradientUnits="userSpaceOnUse"
            x1={dc.x1}
            y1={dc.y1}
            x2={dc.x2}
            y2={dc.y2}
          >
            <stop offset="0%" stopColor="white" stopOpacity="1" />
            <stop offset="60%" stopColor="white" stopOpacity="1" />
            <stop offset="85%" stopColor="white" stopOpacity="0.35" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </linearGradient>
        ))}
        {(decoCables || []).map((dc) => (
          <mask key={dc.id} id={`oDecoMask_${dc.id}`}>
            <rect x="0" y="0" width={w} height={h} fill={`url(#oDecoFade_${dc.id})`} />
          </mask>
        ))}
      </defs>
      {/* Decorative background cables — rendered first, behind everything */}
      {(decoCables || []).map((dc) => {
        const d = cablePath(dc.x1, dc.y1, dc.x2, dc.y2);
        const dHL = cableHL(dc.x1, dc.y1, dc.x2, dc.y2);
        return (
          <g key={dc.id} opacity="0.32" mask={`url(#oDecoMask_${dc.id})`}>
            <path
              d={d}
              fill="none"
              stroke="#334155"
              strokeWidth="12"
              opacity="0.12"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#94a3b8"
              strokeWidth="8"
              opacity="0.5"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="4"
              opacity="0.75"
              strokeLinecap="round"
            />
            <path
              d={dHL}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.5"
              opacity="0.55"
              strokeLinecap="round"
            />
          </g>
        );
      })}
      {cables.map((c) => {
        const color = c.connected ? c.color : "#94a3b8";
        const shadow = c.connected ? c.shadow : "#334155";
        const inner = c.connected ? lv.bg : "#e2e8f0";
        const d = cablePath(c.x1, c.y1, c.x2, c.y2);
        const dHL = cableHL(c.x1, c.y1, c.x2, c.y2);
        return (
          <g key={c.id} opacity={c.connected ? 1 : 0.38}>
            <path
              d={d}
              fill="none"
              stroke={shadow}
              strokeWidth="14"
              opacity="0.16"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={color}
              strokeWidth="9"
              opacity="0.55"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={inner}
              strokeWidth="5"
              opacity="0.80"
              strokeLinecap="round"
            />
            <path
              d={dHL}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.8"
              opacity="0.60"
              strokeLinecap="round"
            />
            <circle cx={c.x1} cy={c.y1} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x1} cy={c.y1} r="2.4" fill="#fff" opacity="0.85" />
            <circle cx={c.x2} cy={c.y2} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x2} cy={c.y2} r="2.4" fill="#fff" opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}
// ── Reusable clickable field row for overview panels ───────────────────────────
interface PanelFieldRowProps {
  label: string;
  value: string | null | undefined;
  emptyText?: string;
  filled: boolean;
  dotColor: string;
  dotGlow: string;
  labelColor: string;
  labelBg: string;
  labelBorderColor: string;
  onClick?: () => void;
  isLast?: boolean;
}
function PanelFieldRow({
  label,
  value,
  emptyText = "not set",
  filled,
  dotColor,
  dotGlow,
  labelColor,
  labelBg,
  labelBorderColor,
  onClick,
  isLast,
}: PanelFieldRowProps) {
  const [hovered, setHovered] = React.useState(false);
  const [tooltipPos, setTooltipPos] = React.useState<{ x: number; y: number } | null>(null);
  const [isOverflowing, setIsOverflowing] = React.useState(false);
  const rowRef = React.useRef<HTMLButtonElement>(null);
  const valueRef = React.useRef<HTMLSpanElement>(null);

  const showTooltip = hovered && filled && value && isOverflowing;

  const handleMouseEnter = (e: React.MouseEvent<HTMLButtonElement>) => {
    setHovered(true);
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.left, y: rect.top });
    if (valueRef.current) {
      setIsOverflowing(valueRef.current.scrollWidth > valueRef.current.offsetWidth);
    }
  };
  const handleMouseLeave = () => {
    setHovered(false);
    setTooltipPos(null);
  };

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        ref={rowRef}
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          display: "flex",
          alignItems: "stretch",
          width: "100%",
          textAlign: "left",
          background: hovered && onClick ? C.surfaceAlt : "transparent",
          border: "none",
          borderBottom: isLast ? "none" : `1px solid ${C.border}`,
          cursor: onClick ? "pointer" : "default",
          transition: "background 0.12s",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 8px",
            minWidth: 80,
            maxWidth: 80,
            flexShrink: 0,
            borderRight: `1px solid ${filled ? labelBorderColor : C.border}`,
            background: filled ? labelBg : "transparent",
          }}
        >
          <div
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              flexShrink: 0,
              background: filled ? dotColor : "#d1d5db",
              boxShadow: filled ? `0 0 5px ${dotGlow}` : "none",
            }}
          />
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              color: filled ? labelColor : C.textMuted,
              fontWeight: 600,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {label}
          </span>
        </div>
        <div style={{ padding: "4px 8px", flex: 1, minWidth: 0 }}>
          <span
            ref={valueRef}
            style={{
              fontSize: 10,
              fontFamily: F.mono,
              color: filled ? C.textMid : C.textMuted,
              fontStyle: filled ? "normal" : "italic",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "block",
            }}
          >
            {filled ? value : emptyText}
          </span>
        </div>
      </button>
      {showTooltip && tooltipPos && (
        <div
          style={{
            position: "fixed",
            left: tooltipPos.x,
            top: tooltipPos.y - 34,
            zIndex: 9999,
            background: C.text,
            color: "#fff",
            fontFamily: F.mono,
            fontSize: 11,
            padding: "5px 9px",
            borderRadius: 6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            maxWidth: 320,
            boxShadow: "0 4px 16px rgba(0,0,0,0.22)",
            pointerEvents: "none",
            lineHeight: 1.5,
          }}
        >
          {value}
          <div
            style={{
              position: "absolute",
              bottom: -5,
              left: 14,
              width: 10,
              height: 10,
              background: C.text,
              transform: "rotate(45deg)",
              borderRadius: 1,
            }}
          />
        </div>
      )}
    </div>
  );
}

interface PageOverviewProps {
  ree: Ree;
  onReeChange: (ree: Ree) => void;
  level: number;
  onNavigate: (key: string) => void;
  badges?: Badges;
  timestamps?: Timestamps;
  onGoField: (key: string) => void;
  files?: FileTreeNode[];
  snapshotFiles?: FileTreeNode[];
  locked?: boolean;
  onSeal: () => void;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
}
function PageOverview({
  ree,
  onReeChange,
  level,
  onNavigate,
  badges = {},
  timestamps = {},
  onGoField,
  files = [],
  snapshotFiles = [],
  locked = false,
  onSeal,
  onPreviewReviewer,
  onDownloadRee,
}: PageOverviewProps) {
  const [showSealConfirm, setShowSealConfirm] = React.useState(false);
  const lv = LEVELS[Math.min(level, 7)];
  const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
    ...S_PANEL,
    ...extra,
  });

  // Cable overlay refs
  const cableContainerRef = useRef<HTMLDivElement>(null);
  const sourceRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const podColumnRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);

  // Responsive pod size — track center column width via ResizeObserver
  const [podSize, setPodSize] = React.useState(480);
  React.useEffect(() => {
    const el = podColumnRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      // Clamp: min 260 so the pod stays readable, max 620 so it doesn't overwhelm
      setPodSize(Math.min(640, Math.max(260, w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const swhRef = useRef<HTMLDivElement>(null);
  const evaluateRef = useRef<HTMLDivElement>(null);
  const sbomRef = useRef<HTMLDivElement>(null);
  const sealRef = useRef<HTMLDivElement>(null);
  const archiveRef = useRef<HTMLDivElement>(null);
  const activationRef = useRef<HTMLDivElement>(null);

  // Source panel state
  const sourceInWorkspace = !!ree._sourceAvailable;
  const sourceFromUpload = ree._sourceAcquiredBy === "upload" && !!ree._sourceAvailable;
  const sourceFromDownload = ree._sourceAcquiredBy === "download" && !!ree._sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";
  const sourceIncluded = sourceInWorkspace && !!ree._sourceIncluded;
  const canIncludeSource = sourceInWorkspace;
  const toggleSource = () => {
    if (!canIncludeSource) return;
    onReeChange && onReeChange({ ...ree, _sourceIncluded: !sourceIncluded });
  };

  useEffect(() => {
    if (!sourceInWorkspace && ree._sourceIncluded) {
      onReeChange && onReeChange({ ...ree, _sourceIncluded: false });
    }
  }, [sourceInWorkspace, ree._sourceIncluded]);

  // Runtime panel state
  const runtimeVal = ree && ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime.trim() : "";
  const runtimeIncluded = !!(ree && ree._runtimeIncluded);
  const canIncludeRuntime = !!runtimeVal;
  const toggleRuntime = () => {
    if (!canIncludeRuntime) return;
    onReeChange && onReeChange({ ...ree, _runtimeIncluded: !runtimeIncluded });
  };

  // Find runtime file in virtual tree and get its mock size
  function findFile(nodes: FileTreeNode[], name: string): FileTreeNode | null {
    for (const n of nodes || []) {
      if (n.type === "file" && n.name === name) return n;
      if (n.children) {
        const r = findFile(n.children, name);
        if (r) return r;
      }
    }
    return null;
  }
  const runtimeFile = runtimeVal ? findFile(files, runtimeVal.split("/").pop()) : null;
  // Extract mock size string if present in content, else estimate from content length
  const runtimeSizeStr = (() => {
    if (!runtimeFile) return null;
    const m = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
    if (m) return m[1];
    return fmtBytes(new TextEncoder().encode(runtimeFile.content || "").length);
  })();

  // SBOM metadata
  const sbomVal = ree && ree.sbom ? ree.sbom.trim() : "";
  const sbomFile = sbomVal ? findFile(files, sbomVal.split("/").pop()) : null;
  const sbomMeta = (() => {
    if (!sbomFile) return null;
    try {
      const parsed = JSON.parse(sbomFile.content || "{}");
      const pkgCount = Array.isArray(parsed.packages)
        ? parsed.packages.length
        : Array.isArray(parsed.components)
          ? parsed.components.length
          : null;
      const fmt = parsed.spdxVersion
        ? `SPDX ${parsed.spdxVersion.replace("SPDX-", "")}`
        : parsed.bomFormat === "CycloneDX"
          ? `CycloneDX ${parsed.specVersion || ""}`
          : parsed.descriptor?.name === "syft"
            ? "Syft JSON"
            : "JSON";
      return { pkgCount, fmt };
    } catch {
      return null;
    }
  })();

  // Compute source file stats
  function flatFiles(nodes: FileTreeNode[]): FileTreeNode[] {
    const out = [];
    for (const n of nodes || []) {
      if (n.type === "file") out.push(n);
      else if (n.children) out.push(...flatFiles(n.children));
    }
    return out;
  }
  const allFiles = flatFiles(snapshotFiles);
  const fileCount = allFiles.length;
  const totalBytes = allFiles.reduce(
    (s, f) => s + (f.content ? new TextEncoder().encode(f.content).length : 0),
    0,
  );
  function fmtBytes(b: number): string {
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / (1024 * 1024)).toFixed(2)} MB`;
  }

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 20, display: "flex", alignItems: "baseline", gap: 14 }}>
        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: C.textMuted,
              letterSpacing: 1.2,
              textTransform: "uppercase",
              fontFamily: F.sans,
              marginBottom: 4,
            }}
          >
            Reproducible Execution Environment
          </div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 800,
              color: C.text,
              letterSpacing: 0.2,
              fontFamily: F.mono,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            {ree.name || "untitled-env"}
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 3,
                background: `${lv.color}16`,
                color: lv.color,
                border: `1px solid ${lv.color}40`,
                letterSpacing: 1.5,
                textTransform: "uppercase",
              }}
            >
              {lv.label}
            </span>
          </div>
        </div>
        <div style={{ flex: 1, height: 1, background: C.border, marginBottom: 2 }} />
        <div style={{ fontSize: 9, fontFamily: F.mono, color: C.textMuted, letterSpacing: 1 }}>
          {new Date().toISOString().slice(0, 10)}
        </div>
      </div>

      {/* ── Three columns ── */}
      <div
        ref={cableContainerRef}
        style={{ display: "flex", alignItems: "flex-start", gap: 18, position: "relative" }}
      >
        <PanelCableOverlay
          containerRef={cableContainerRef}
          sourceRef={sourceRef}
          runtimeRef={runtimeRef}
          metadataRef={leftPanelRef}
          swhRef={swhRef}
          evaluateRef={evaluateRef}
          sbomRef={sbomRef}
          sealRef={sealRef}
          archiveRef={archiveRef}
          activationRef={activationRef}
          podSvgRef={podSvgRef}
          level={level}
          badges={badges}
          ree={ree}
        />

        {/* Left — source + fields */}
        <div
          style={{
            width: 196,
            flexShrink: 0,
            position: "relative",
            zIndex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {/* Source panel */}
          <div ref={sourceRef} style={panel({ overflow: "hidden" })}>
            <div
              style={{
                padding: "8px 12px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: sourceIncluded ? "#f59e0b" : "#d1d5db",
                  boxShadow: sourceIncluded ? "0 0 5px #f59e0b99" : "none",
                  transition: "all 0.2s",
                }}
              />
              <span style={S_PANEL_HEADER_LABEL}>Source</span>
              <div
                style={{
                  marginLeft: "auto",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  opacity: canIncludeSource ? 1 : 0.45,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontFamily: F.sans,
                    fontWeight: 600,
                    color: sourceIncluded ? "#92400e" : C.textMuted,
                    letterSpacing: 0.3,
                  }}
                >
                  {sourceIncluded ? "Included" : "Include"}
                </span>
                <button
                  type="button"
                  onClick={toggleSource}
                  aria-pressed={sourceIncluded}
                  disabled={!canIncludeSource}
                  style={{
                    width: 32,
                    height: 16,
                    borderRadius: 99,
                    border: "none",
                    cursor: canIncludeSource ? "pointer" : "not-allowed",
                    background: sourceIncluded ? "#f59e0b" : C.borderMid,
                    position: "relative",
                    transition: "all 0.18s",
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => {
                    if (!sourceIncluded && canIncludeSource)
                      (e.currentTarget.style as any).filter = "brightness(0.93)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget.style as any).filter = "none";
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: 2,
                      left: sourceIncluded ? 16 : 2,
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      background: "#fff",
                      transition: "left 0.18s",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
                    }}
                  />
                </button>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <PanelFieldRow
                label="Origin URL"
                value={ree.origin_url || null}
                filled={!!ree.origin_url}
                dotColor="#f59e0b"
                dotGlow="#f59e0b99"
                labelColor="#92400e"
                labelBg="#fffbeb"
                labelBorderColor="#f59e0b25"
                onClick={() => onGoField && onGoField("origin_url")}
              />
              <PanelFieldRow
                label="Origin Provisioning Status"
                value={sourceProvisionStatus}
                filled={!!ree._sourceAcquiredBy}
                dotColor="#f59e0b"
                dotGlow="#f59e0b99"
                labelColor="#92400e"
                labelBg="#fffbeb"
                labelBorderColor="#f59e0b25"
                onClick={() => onGoField && onGoField("_sourceAcquiredBy")}
              />
              <PanelFieldRow
                label="Origin Type"
                value={ree.source_type || null}
                filled={!!ree.source_type}
                dotColor="#f59e0b"
                dotGlow="#f59e0b99"
                labelColor="#92400e"
                labelBg="#fffbeb"
                labelBorderColor="#f59e0b25"
                onClick={() => onGoField && onGoField("source_type")}
              />
              <PanelFieldRow
                label="Files"
                value={
                  ree._sourceAvailable
                    ? fileCount > 0
                      ? `${fileCount} file${fileCount !== 1 ? "s" : ""} · ${fmtBytes(totalBytes)}`
                      : "downloaded"
                    : null
                }
                filled={!!ree._sourceAvailable}
                dotColor="#f59e0b"
                dotGlow="#f59e0b99"
                labelColor="#92400e"
                labelBg="#fffbeb"
                labelBorderColor="#f59e0b25"
                emptyText="not downloaded"
                isLast
                onClick={() => onNavigate && onNavigate(PAGE.SOURCE)}
              />
            </div>
            <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.border}` }}>
              <button
                type="button"
                onClick={() => onNavigate && onNavigate(PAGE.SOURCE)}
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  color: "#92400e",
                  background: "#fffbeb",
                  border: "1px solid #f59e0b40",
                  borderRadius: 5,
                  padding: "4px 8px",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: 600,
                  width: "100%",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
              >
                → Go to Source
              </button>
            </div>
          </div>

          {/* Metadata panel */}
          <div ref={leftPanelRef} style={panel({ overflow: "hidden" })}>
            <div
              style={{
                padding: "8px 12px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e" }} />
              <span style={S_PANEL_HEADER_LABEL}>Metadata</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 8,
                  fontFamily: F.mono,
                  color: C.textMuted,
                  letterSpacing: 0.5,
                }}
              >
                {
                  (["name", "hardware_description"] as (keyof Ree)[]).filter((f) =>
                    f === "hardware_description"
                      ? Object.values((ree[f] as Record<string, string>) || {}).some((v) => v)
                      : !!ree[f],
                  ).length
                }
                /2
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {(["name", "hardware_description"] as (keyof Ree)[]).map((f, fi) => {
                const isHw = f === "hardware_description";
                const rawVal = ree[f];
                const filled = isHw
                  ? Object.values((rawVal as Record<string, string>) || {}).some((v) => v)
                  : !!rawVal;
                const label = FIELD_META[f as string]?.label || (isHw ? "Hardware" : String(f));
                const displayVal = isHw
                  ? Object.entries((rawVal as Record<string, string>) || {})
                      .filter(([, v]) => v)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")
                  : String(rawVal ?? "");
                return (
                  <PanelFieldRow
                    key={f}
                    label={label}
                    value={filled ? displayVal : null}
                    filled={filled}
                    dotColor="#22c55e"
                    dotGlow="#22c55e99"
                    labelColor="#15803d"
                    labelBg="#f0fdf4"
                    labelBorderColor="#22c55e25"
                    isLast={fi === 1}
                    onClick={() => (onGoField ? onGoField(f) : undefined)}
                  />
                );
              })}
            </div>
            <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
              <button
                type="button"
                onClick={() => onNavigate && onNavigate(PAGE.METADATA)}
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  color: C.text,
                  background: "#f0fdf4",
                  border: `1px solid ${C.border}40`,
                  borderRadius: 5,
                  padding: "4px 8px",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: 600,
                  marginTop: 2,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
              >
                → Edit Metadata
              </button>
            </div>
          </div>

          {/* Runtime panel */}
          <div ref={runtimeRef} style={panel({ overflow: "hidden" })}>
            <div
              style={{
                padding: "8px 12px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: runtimeIncluded ? "#0891b2" : "#d1d5db",
                  boxShadow: runtimeIncluded ? "0 0 5px #0891b299" : "none",
                  transition: "all 0.2s",
                }}
              />
              <span style={S_PANEL_HEADER_LABEL}>Runtime</span>
              <div
                style={{
                  marginLeft: "auto",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  opacity: canIncludeRuntime ? 1 : 0.45,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontFamily: F.sans,
                    fontWeight: 600,
                    color: runtimeIncluded ? "#164e63" : C.textMuted,
                    letterSpacing: 0.3,
                  }}
                >
                  {runtimeIncluded ? "Included" : "Include"}
                </span>
                <button
                  type="button"
                  onClick={toggleRuntime}
                  aria-pressed={runtimeIncluded}
                  disabled={!canIncludeRuntime}
                  style={{
                    width: 32,
                    height: 16,
                    borderRadius: 99,
                    border: "none",
                    cursor: canIncludeRuntime ? "pointer" : "not-allowed",
                    background: runtimeIncluded ? "#0891b2" : C.borderMid,
                    position: "relative",
                    transition: "all 0.18s",
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => {
                    if (!runtimeIncluded && canIncludeRuntime)
                      (e.currentTarget.style as any).filter = "brightness(0.93)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget.style as any).filter = "none";
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: 2,
                      left: runtimeIncluded ? 16 : 2,
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      background: "#fff",
                      transition: "left 0.18s",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
                    }}
                  />
                </button>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <PanelFieldRow
                label="Runtime"
                value={runtimeVal || null}
                filled={!!runtimeVal}
                dotColor="#0891b2"
                dotGlow="#0891b299"
                labelColor="#164e63"
                labelBg="#ecfeff"
                labelBorderColor="#0891b225"
                emptyText="not set"
                onClick={() => onNavigate && onNavigate(PAGE.BUILD)}
              />
              {runtimeSizeStr && (
                <PanelFieldRow
                  label="Size"
                  value={runtimeSizeStr}
                  filled={!!runtimeSizeStr}
                  dotColor="#0891b2"
                  dotGlow="#0891b299"
                  labelColor="#164e63"
                  labelBg="#ecfeff"
                  labelBorderColor="#0891b225"
                  onClick={() => onNavigate && onNavigate(PAGE.BUILD)}
                />
              )}
              <PanelFieldRow
                label="Build Script"
                value={ree.build_runtime_script || null}
                filled={!!ree.build_runtime_script}
                dotColor="#0891b2"
                dotGlow="#0891b299"
                labelColor="#164e63"
                labelBg="#ecfeff"
                labelBorderColor="#0891b225"
                emptyText="not set"
                isLast
                onClick={() => onGoField && onGoField("build_runtime_script")}
              />
            </div>
            {/* Go to Build Runtime button */}
            <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.border}` }}>
              <button
                type="button"
                onClick={() => onNavigate && onNavigate(PAGE.BUILD)}
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  color: "#0891b2",
                  background: "#ecfeff",
                  border: "1px solid #a5f3fc",
                  borderRadius: 5,
                  padding: "4px 8px",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: 600,
                  width: "100%",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
              >
                → Go to Build Runtime
              </button>
            </div>
          </div>

          {/* SBOM panel */}
          {(() => {
            const earned = !!(badges && badges["sbom"]);
            const color = "#16a34a";
            return (
              <div ref={sbomRef} style={panel({ overflow: "hidden" })}>
                <div
                  style={{
                    padding: "8px 12px",
                    borderBottom: `1px solid ${C.border}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: sbomVal ? color : "#d1d5db",
                      boxShadow: sbomVal ? `0 0 5px ${color}99` : "none",
                    }}
                  />
                  <span style={S_PANEL_HEADER_LABEL}>SBOM</span>
                  {earned && (
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 8,
                        fontFamily: F.mono,
                        color,
                        background: "#f0fdf4",
                        border: `1px solid ${color}40`,
                        borderRadius: 2,
                        padding: "0 4px",
                        letterSpacing: 0.8,
                      }}
                    >
                      OK
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <PanelFieldRow
                    label="SBOM Path"
                    value={sbomVal || null}
                    filled={!!sbomVal}
                    dotColor="#16a34a"
                    dotGlow="#16a34a99"
                    labelColor="#15803d"
                    labelBg="#f0fdf4"
                    labelBorderColor="#16a34a25"
                    emptyText="not set"
                    onClick={() => onNavigate && onNavigate(PAGE.SBOM)}
                  />
                  {sbomMeta?.fmt && (
                    <PanelFieldRow
                      label="Format"
                      value={sbomMeta.fmt}
                      filled
                      dotColor="#16a34a"
                      dotGlow="#16a34a99"
                      labelColor="#15803d"
                      labelBg="#f0fdf4"
                      labelBorderColor="#16a34a25"
                      onClick={() => onNavigate && onNavigate(PAGE.SBOM)}
                    />
                  )}
                  {sbomMeta?.pkgCount != null && (
                    <PanelFieldRow
                      label="Packages"
                      value={`${sbomMeta.pkgCount} pkg${sbomMeta.pkgCount !== 1 ? "s" : ""}`}
                      filled
                      dotColor="#16a34a"
                      dotGlow="#16a34a99"
                      labelColor="#15803d"
                      labelBg="#f0fdf4"
                      labelBorderColor="#16a34a25"
                      isLast
                      onClick={() => onNavigate && onNavigate(PAGE.SBOM)}
                    />
                  )}
                </div>
                <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.border}` }}>
                  <button
                    type="button"
                    onClick={() => onNavigate && onNavigate(PAGE.SBOM)}
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      color,
                      background: "#f0fdf4",
                      border: `1px solid ${color}40`,
                      borderRadius: 5,
                      padding: "4px 8px",
                      cursor: "pointer",
                      textAlign: "center",
                      fontWeight: 600,
                      width: "100%",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                    onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                  >
                    → Generate SBOM
                  </button>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Center — pod + artifact bar + status */}
        <div
          ref={podColumnRef}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            minWidth: 0,
            position: "relative",
            zIndex: 1,
          }}
        >
          <PodWidget level={level} svgRef={podSvgRef} size={podSize} />

          {/* ── Seal strip ── */}
          {(() => {
            const sealed = locked && ree._sealedAt;
            const cableItems = [
              {
                key: PAGE.METADATA,
                label: "Metadata",
                live:
                  (["name", "hardware_description"] as (keyof Ree)[]).filter((f) =>
                    f === "hardware_description"
                      ? Object.values((ree[f] as Record<string, string>) || {}).some((v) => v)
                      : !!ree[f],
                  ).length > 0,
              },
              { key: PAGE.SOURCE, label: "Source", live: !!ree._sourceAvailable },
              { key: "runtime", label: "Runtime", live: !!ree._runtimeIncluded },
              { key: "swh", label: "Software Heritage", live: !!ree.swhid },
              { key: "sbom", label: "SBOM", live: !!ree.sbom },
              { key: "evaluate", label: "Evaluate", live: !!(badges && badges["evaluate"]) },
              {
                key: "archive",
                label: "Archival & DOIs",
                live: !!(ree.zenodo_doi || ree.dataverse_doi),
              },
              {
                key: "activation",
                label: "Test Activation",
                live: !!(badges && badges["activation"]),
              },
            ];
            const liveCount = cableItems.filter((c) => c.live).length;
            const totalCables = cableItems.length;
            const allLive = liveCount === totalCables;
            const missing = cableItems.filter((c) => !c.live);
            const lv = LEVELS[Math.min(level, 7)];

            if (sealed) {
              const sealDate = new Date(ree._sealedAt).toLocaleString([], {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });
              return (
                <div
                  ref={sealRef}
                  style={{
                    width: "100%",
                    maxWidth: 480,
                    background: C.surface,
                    border: `1.5px solid ${lv.color}50`,
                    borderRadius: 10,
                    overflow: "hidden",
                    boxShadow: `0 0 0 3px ${lv.color}14, 0 2px 12px rgba(0,0,0,0.07)`,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "9px 14px",
                      borderBottom: `1px solid ${lv.color}30`,
                      background: `${lv.color}0c`,
                    }}
                  >
                    <span style={{ color: lv.color, display: "flex", flexShrink: 0 }}>
                      {Ic.lock(13)}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        fontFamily: F.sans,
                        color: lv.color,
                        letterSpacing: 0.4,
                      }}
                    >
                      REE SEALED
                    </span>
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 9,
                        fontFamily: F.mono,
                        color: lv.color,
                        background: `${lv.color}18`,
                        border: `1px solid ${lv.color}40`,
                        borderRadius: 3,
                        padding: "1px 6px",
                        letterSpacing: 0.6,
                        fontWeight: 700,
                      }}
                    >
                      L{level} · {lv.label}
                    </span>
                  </div>
                  <div
                    style={{
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          fontSize: 9,
                          fontFamily: F.sans,
                          color: C.textMuted,
                          flexShrink: 0,
                        }}
                      >
                        hash
                      </span>
                      <span
                        style={{
                          fontFamily: F.mono,
                          fontSize: 11,
                          color: C.text,
                          fontWeight: 600,
                          letterSpacing: 0.8,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ree._sealHash || "—"}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          fontSize: 9,
                          fontFamily: F.sans,
                          color: C.textMuted,
                          flexShrink: 0,
                        }}
                      >
                        sealed
                      </span>
                      <span style={{ fontFamily: F.mono, fontSize: 10, color: C.textMid }}>
                        {sealDate}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 3, marginTop: 2 }}>
                      {cableItems.map((c, i) => (
                        <div
                          key={i}
                          title={c.label}
                          style={{
                            flex: 1,
                            height: 3,
                            borderRadius: 99,
                            background: c.live ? lv.color : "#d1d5db",
                            opacity: c.live ? 0.85 : 0.4,
                          }}
                        />
                      ))}
                    </div>
                    {onPreviewReviewer && (
                      <button
                        type="button"
                        onClick={onPreviewReviewer}
                        style={{
                          marginTop: 6,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 7,
                          width: "100%",
                          padding: "8px 14px",
                          borderRadius: 7,
                          background: `linear-gradient(135deg, ${lv.color}18 0%, ${lv.color}0c 100%)`,
                          border: `1.5px solid ${lv.color}50`,
                          color: lv.color,
                          fontSize: 12,
                          fontWeight: 700,
                          fontFamily: F.sans,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = `${lv.color}28`;
                          e.currentTarget.style.borderColor = `${lv.color}80`;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = `linear-gradient(135deg, ${lv.color}18 0%, ${lv.color}0c 100%)`;
                          e.currentTarget.style.borderColor = `${lv.color}50`;
                        }}
                      >
                        {Ic.star(12)}
                        Preview as Reviewer
                      </button>
                    )}
                    {onDownloadRee && (
                      <button
                        type="button"
                        onClick={onDownloadRee}
                        style={{
                          marginTop: 6,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 7,
                          width: "100%",
                          padding: "8px 14px",
                          borderRadius: 7,
                          background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
                          border: "1.5px solid #86efac",
                          color: "#15803d",
                          fontSize: 12,
                          fontWeight: 700,
                          fontFamily: F.sans,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "#bbf7d0";
                          e.currentTarget.style.borderColor = "#4ade80";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background =
                            "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)";
                          e.currentTarget.style.borderColor = "#86efac";
                        }}
                      >
                        {Ic.download(12)}
                        Download REE
                      </button>
                    )}
                  </div>
                </div>
              );
            }

            return (
              <>
                {/* Confirmation modal */}
                {showSealConfirm && (
                  <div
                    style={{
                      position: "fixed",
                      inset: 0,
                      zIndex: 9999,
                      background: "rgba(0,0,0,0.45)",
                      backdropFilter: "blur(3px)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                    onClick={(e) => {
                      if (e.target === e.currentTarget) setShowSealConfirm(false);
                    }}
                  >
                    <div
                      style={{
                        background: C.surface,
                        borderRadius: 14,
                        width: 380,
                        maxWidth: "90vw",
                        border: `1.5px solid ${C.border}`,
                        boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
                        overflow: "hidden",
                      }}
                    >
                      {/* Modal header */}
                      <div
                        style={{ padding: "16px 20px 12px", borderBottom: `1px solid ${C.border}` }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 8,
                              background: `${lv.color}18`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <span style={{ color: lv.color, display: "flex" }}>{Ic.lock(16)}</span>
                          </div>
                          <div>
                            <div
                              style={{
                                fontSize: 14,
                                fontWeight: 700,
                                fontFamily: F.sans,
                                color: C.text,
                              }}
                            >
                              Seal this REE?
                            </div>
                            <div
                              style={{
                                fontSize: 11,
                                fontFamily: F.sans,
                                color: C.textMuted,
                                marginTop: 1,
                              }}
                            >
                              This action cannot be undone.
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Warning: missing cables */}
                      {!allLive && (
                        <div
                          style={{
                            margin: "12px 20px 0",
                            padding: "10px 12px",
                            borderRadius: 8,
                            background: "#fffbeb",
                            border: "1.5px solid #fde68a",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                            <span style={{ fontSize: 15, flexShrink: 0, lineHeight: 1.2 }}>⚠️</span>
                            <div>
                              <div
                                style={{
                                  fontSize: 11,
                                  fontWeight: 700,
                                  fontFamily: F.sans,
                                  color: "#92400e",
                                  marginBottom: 5,
                                }}
                              >
                                {missing.length} panel{missing.length !== 1 ? "s" : ""} not
                                connected
                              </div>
                              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                                {missing.map((m) => (
                                  <div
                                    key={m.key}
                                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                                  >
                                    <div
                                      style={{
                                        width: 5,
                                        height: 5,
                                        borderRadius: "50%",
                                        background: "#f59e0b",
                                        flexShrink: 0,
                                      }}
                                    />
                                    <span
                                      style={{ fontSize: 10, fontFamily: F.sans, color: "#92400e" }}
                                    >
                                      {m.label} — not completed
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Body copy */}
                      <div style={{ padding: "12px 20px" }}>
                        <div
                          style={{
                            fontSize: 12,
                            fontFamily: F.sans,
                            color: C.textMid,
                            lineHeight: 1.6,
                          }}
                        >
                          {allLive ? (
                            <>
                              All <strong>{totalCables}</strong> panels are connected. The REE will
                              be frozen at{" "}
                              <strong>
                                L{level} · {lv.label}
                              </strong>{" "}
                              and become read-only.
                            </>
                          ) : (
                            <>
                              Sealing now will freeze the REE at{" "}
                              <strong>
                                L{level} · {lv.label}
                              </strong>{" "}
                              with incomplete data. You can still seal, but the missing panels will
                              not be part of the record.
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div
                        style={{
                          padding: "0 20px 16px",
                          display: "flex",
                          gap: 8,
                          justifyContent: "flex-end",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setShowSealConfirm(false)}
                          style={{
                            padding: "8px 16px",
                            borderRadius: 7,
                            fontSize: 12,
                            fontFamily: F.sans,
                            fontWeight: 600,
                            cursor: "pointer",
                            background: C.surfaceAlt,
                            color: C.textMid,
                            border: `1.5px solid ${C.border}`,
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = C.border)}
                          onMouseLeave={(e) => (e.currentTarget.style.background = C.surfaceAlt)}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowSealConfirm(false);
                            onSeal && onSeal();
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 7,
                            padding: "8px 18px",
                            borderRadius: 7,
                            fontSize: 12,
                            fontFamily: F.sans,
                            fontWeight: 700,
                            cursor: "pointer",
                            background: lv.color,
                            color: "#fff",
                            border: `1.5px solid ${lv.color}`,
                            boxShadow: `0 2px 8px ${lv.color}50`,
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.9)")}
                          onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                        >
                          <span style={{ display: "flex" }}>{Ic.lock(12)}</span>
                          {allLive ? "Seal REE" : "Seal anyway"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Seal strip */}
                <div
                  ref={sealRef}
                  style={{
                    width: "100%",
                    maxWidth: 480,
                    background: C.surface,
                    border: `1.5px solid ${C.border}`,
                    borderRadius: 10,
                    overflow: "hidden",
                  }}
                >
                  {/* Progress row */}
                  <div
                    style={{
                      padding: "9px 14px",
                      borderBottom: `1px solid ${C.border}`,
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: C.textMuted,
                        flexShrink: 0,
                      }}
                    >
                      {liveCount}/{totalCables} connected
                    </span>
                    <div style={{ flex: 1, display: "flex", gap: 3, alignItems: "center" }}>
                      {cableItems.map((c, i) => (
                        <div
                          key={i}
                          title={c.label}
                          style={{
                            flex: 1,
                            height: 3,
                            borderRadius: 99,
                            background: c.live ? lv.color : C.border,
                            transition: "background 0.3s",
                          }}
                        />
                      ))}
                    </div>
                    {allLive ? (
                      <span
                        style={{
                          fontSize: 9,
                          fontFamily: F.mono,
                          fontWeight: 700,
                          color: lv.color,
                          background: `${lv.color}14`,
                          border: `1px solid ${lv.color}40`,
                          borderRadius: 3,
                          padding: "1px 6px",
                          letterSpacing: 0.5,
                          flexShrink: 0,
                        }}
                      >
                        ready
                      </span>
                    ) : (
                      <span
                        style={{
                          fontSize: 9,
                          fontFamily: F.mono,
                          fontWeight: 700,
                          color: "#d97706",
                          background: "#fffbeb",
                          border: "1px solid #fde68a",
                          borderRadius: 3,
                          padding: "1px 6px",
                          letterSpacing: 0.5,
                          flexShrink: 0,
                        }}
                      >
                        incomplete
                      </span>
                    )}
                  </div>
                  {/* Seal button row */}
                  <div
                    style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <div style={{ flex: 1 }}>
                      <div
                        style={{ fontSize: 11, fontFamily: F.sans, fontWeight: 600, color: C.text }}
                      >
                        Seal REE
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          fontFamily: F.sans,
                          color: allLive ? C.textMuted : "#d97706",
                          marginTop: 2,
                        }}
                      >
                        {allLive
                          ? `L${level} · ${lv.label} — all panels connected`
                          : `${missing.length} panel${missing.length !== 1 ? "s" : ""} not yet connected`}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowSealConfirm(true)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 7,
                        padding: "8px 18px",
                        borderRadius: 7,
                        flexShrink: 0,
                        fontSize: 12,
                        fontFamily: F.sans,
                        fontWeight: 700,
                        letterSpacing: 0.3,
                        cursor: "pointer",
                        background: lv.color,
                        color: "#fff",
                        border: `1.5px solid ${lv.color}`,
                        boxShadow: `0 2px 10px ${lv.color}50`,
                        transition: "all 0.2s",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.92)")}
                      onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                    >
                      <span style={{ display: "flex" }}>{Ic.lock(13)}</span>
                      Seal
                    </button>
                  </div>
                </div>
              </>
            );
          })()}
        </div>

        {/* Right — swh + evaluate + archive + verification */}
        <div
          style={{
            width: 196,
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            gap: 14,
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* Software Heritage panel */}
          <div ref={swhRef} style={panel({ overflow: "hidden" })}>
            <div
              style={{
                padding: "8px 12px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: "#e4572e",
                  boxShadow: ree.swhid ? "0 0 5px #e4572e99" : "none",
                }}
              />
              <span style={S_PANEL_HEADER_LABEL}>Software Heritage</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 8,
                  fontFamily: F.mono,
                  color: "#e4572e",
                  background: "#fff7f5",
                  border: "1px solid #fbd0c4",
                  borderRadius: 2,
                  padding: "0 4px",
                  letterSpacing: 0.8,
                }}
              >
                SWH
              </span>
            </div>
            <PanelFieldRow
              label="SWHID"
              value={ree.swhid || null}
              filled={!!ree.swhid}
              dotColor="#e4572e"
              dotGlow="#e4572e99"
              labelColor="#9a3412"
              labelBg="#fff7f5"
              labelBorderColor="#e4572e25"
              emptyText="not archived"
              isLast
              onClick={() => onNavigate && onNavigate(PAGE.SWH)}
            />
            <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.border}` }}>
              <button
                type="button"
                onClick={() => onNavigate && onNavigate(PAGE.SWH)}
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  color: "#9a3412",
                  background: "#fff7f5",
                  border: "1px solid #fbd0c4",
                  borderRadius: 5,
                  padding: "4px 8px",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: 600,
                  width: "100%",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
              >
                → Go to Software Heritage
              </button>
            </div>
          </div>

          {/* Evaluate panel */}
          {(() => {
            const svc = EVALUATE_SVC;
            const earned = !!badges[svc.key];
            const ts = timestamps[svc.key];
            const dateStr = ts
              ? new Date(ts).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : null;
            return (
              <div ref={evaluateRef} style={panel({ overflow: "hidden" })}>
                <div
                  style={{
                    padding: "8px 12px",
                    borderBottom: `1px solid ${C.border}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: earned ? svc.badge.color : "#d1d5db",
                      boxShadow: earned ? `0 0 5px ${svc.badge.color}99` : "none",
                    }}
                  />
                  <span style={S_PANEL_HEADER_LABEL}>Evaluate</span>
                  {earned && (
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 8,
                        fontFamily: F.mono,
                        color: svc.badge.color,
                        background: svc.badge.bg,
                        border: `1px solid ${svc.badge.color}40`,
                        borderRadius: 2,
                        padding: "0 4px",
                        letterSpacing: 0.8,
                      }}
                    >
                      OK
                    </span>
                  )}
                </div>
                <div
                  style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{ display: "flex", color: earned ? svc.badge.color : C.textMuted }}
                    >
                      {Ic.star(12)}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: earned ? C.text : C.textMuted,
                        flex: 1,
                      }}
                    >
                      {earned ? `L${level} — ${LEVELS[Math.min(level, 7)].label}` : "Not evaluated"}
                    </span>
                  </div>
                  {earned && dateStr && (
                    <div
                      style={{
                        fontSize: 9,
                        fontFamily: F.mono,
                        color: C.textMuted,
                        letterSpacing: 0.2,
                      }}
                    >
                      {dateStr}
                    </div>
                  )}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "5px 8px",
                      borderRadius: 5,
                      background: earned ? svc.badge.bg : C.surfaceAlt,
                      border: `1px solid ${earned ? `${svc.badge.color}40` : C.border}`,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: earned ? svc.badge.color : C.textMuted,
                        fontWeight: 600,
                      }}
                    >
                      {earned ? "✓ score computed" : "run Evaluate"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onNavigate && onNavigate(svc.key)}
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      color: svc.badge.color,
                      background: svc.badge.bg,
                      border: `1px solid ${svc.badge.color}40`,
                      borderRadius: 5,
                      padding: "4px 8px",
                      cursor: "pointer",
                      textAlign: "center",
                      fontWeight: 600,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                    onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                  >
                    → Go to Evaluate
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Archival & DOIs — Zenodo + Dataverse only */}
          <div ref={archiveRef} style={panel({ overflow: "hidden" })}>
            <div
              style={{
                padding: "8px 12px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#059669" }} />
              <span style={S_PANEL_HEADER_LABEL}>Archival & DOIs</span>
            </div>
            {[
              {
                label: "Zenodo",
                field: "zenodo_doi" as keyof Ree,
                dotColor: "#3b8fd4",
                dotGlow: "#3b8fd499",
                labelColor: "#1e4d7a",
                labelBg: "#eff6ff",
                labelBorderColor: "#3b8fd425",
              },
              {
                label: "Dataverse",
                field: "dataverse_doi" as keyof Ree,
                dotColor: "#8b6fd4",
                dotGlow: "#8b6fd499",
                labelColor: "#4c1d95",
                labelBg: "#f5f3ff",
                labelBorderColor: "#8b6fd425",
              },
            ].map((r, i) => {
              const val = ree[r.field] as string | undefined;
              const filled = !!(val && val.trim().length > 0);
              return (
                <PanelFieldRow
                  key={r.field}
                  label={r.label}
                  value={filled ? val : null}
                  filled={filled}
                  dotColor={r.dotColor}
                  dotGlow={r.dotGlow}
                  labelColor={r.labelColor}
                  labelBg={r.labelBg}
                  labelBorderColor={r.labelBorderColor}
                  emptyText="unregistered"
                  isLast={i === 1}
                  onClick={() => onNavigate && onNavigate(PAGE.ARCHIVE)}
                />
              );
            })}
            <div style={{ padding: "8px 12px", borderTop: `1px solid ${C.border}` }}>
              <button
                type="button"
                onClick={() => onNavigate && onNavigate(PAGE.ARCHIVE)}
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  color: "#059669",
                  background: "#f0fdf4",
                  border: "1px solid #6ee7b740",
                  borderRadius: 5,
                  padding: "4px 8px",
                  cursor: "pointer",
                  textAlign: "center",
                  fontWeight: 600,
                  width: "100%",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
              >
                → Go to Archival & DOIs
              </button>
            </div>
          </div>

          {/* Test Activation panel */}
          {(() => {
            const activationColor = "#7c3aed";
            const activationEarned = !!badges["activation"];
            const as = ree.activation_script;
            const asFilled = !!as;
            const asLabel = FIELD_META["activation_script"]?.label || "Activation script";
            return (
              <div ref={activationRef} style={panel({ overflow: "hidden" })}>
                <div
                  style={{
                    padding: "8px 12px",
                    borderBottom: `1px solid ${C.border}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: activationColor,
                      boxShadow: activationEarned ? `0 0 5px ${activationColor}99` : "none",
                    }}
                  />
                  <span style={S_PANEL_HEADER_LABEL}>Test Activation</span>
                  {activationEarned && (
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 8,
                        fontFamily: F.mono,
                        color: activationColor,
                        background: "#f5f3ff",
                        border: `1px solid ${activationColor}40`,
                        borderRadius: 2,
                        padding: "0 4px",
                        letterSpacing: 0.8,
                      }}
                    >
                      OK
                    </span>
                  )}
                </div>
                {/* activation_script field row */}
                <PanelFieldRow
                  label={asLabel}
                  value={asFilled ? as : null}
                  filled={asFilled}
                  dotColor="#7c3aed"
                  dotGlow="#7c3aed99"
                  labelColor="#5b21b6"
                  labelBg="#f5f3ff"
                  labelBorderColor="#7c3aed25"
                  isLast
                  onClick={() => onGoField && onGoField("activation_script")}
                />
                {/* Go to Test Activation button */}
                <div style={{ padding: "8px 12px" }}>
                  <button
                    type="button"
                    onClick={() => onNavigate && onNavigate(PAGE.ACTIVATION)}
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      color: activationColor,
                      background: "#f5f3ff",
                      border: `1px solid ${activationColor}40`,
                      borderRadius: 5,
                      padding: "4px 8px",
                      cursor: "pointer",
                      textAlign: "center",
                      fontWeight: 600,
                      width: "100%",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
                    onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
                  >
                    → Go to Test Activation
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Horizontal level strip ── */}
      <div style={{ marginTop: 20, display: "flex", alignItems: "center" }}>
        {LEVELS.map((lv, i) => {
          const isReached = i <= level;
          const isCurrent = i === level;
          const isLast = i === LEVELS.length - 1;
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 5,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    width: isCurrent ? 14 : 9,
                    height: isCurrent ? 14 : 9,
                    borderRadius: "50%",
                    background: isReached ? lv.color : C.border,
                    border: isCurrent ? `2.5px solid ${lv.color}` : "none",
                    boxShadow: isCurrent ? `0 0 0 4px ${lv.color}22` : "none",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.4,
                    color: isReached ? lv.ink : C.textMuted,
                    background: isReached ? `${lv.color}18` : C.surfaceAlt,
                    border: `1px solid ${isReached ? `${lv.color}40` : C.border}`,
                    borderRadius: 3,
                    padding: "0 5px",
                    lineHeight: "18px",
                    whiteSpace: "nowrap",
                  }}
                >
                  L{i}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: isCurrent ? 700 : 400,
                    color: isCurrent ? C.text : isReached ? C.textMid : C.textMuted,
                    fontFamily: F.sans,
                    whiteSpace: "nowrap",
                  }}
                >
                  {lv.label}
                </span>
              </div>
              {!isLast && (
                <div
                  style={{
                    height: 2,
                    flex: 1,
                    maxWidth: 28,
                    background: i < level ? lv.color : C.border,
                    borderRadius: 1,
                    flexShrink: 0,
                    marginBottom: 34,
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* ── All REE Fields (Readonly) ── */}
      <div
        style={{
          marginTop: 32,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "16px 20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.textMuted }} />
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: C.text,
              letterSpacing: 0.3,
              fontFamily: F.sans,
            }}
          >
            All Fields
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {Object.entries(ree)
            .filter(([k]) => !k.startsWith("_"))
            .map(([k, v], idx, arr) => {
              const label = FIELD_META[k]?.label || k;
              const isEmpty =
                v === undefined ||
                v === null ||
                v === "" ||
                (typeof v === "object" && Object.keys(v).length === 0);
              let displayVal = isEmpty ? "not set" : v;
              if (typeof v === "object" && v !== null && !isEmpty) {
                displayVal = JSON.stringify(v, null, 2);
              }
              const isLastRow = idx === arr.length - 1;
              return (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    padding: "10px 0",
                    borderBottom: isLastRow ? "none" : `1px solid ${C.border}`,
                    alignItems: "flex-start",
                    gap: 16,
                  }}
                >
                  <div
                    style={{ width: 180, display: "flex", flexDirection: "column", flexShrink: 0 }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: F.sans,
                        color: C.textMid,
                        fontWeight: 600,
                      }}
                    >
                      {label}
                    </span>
                    <span style={{ fontFamily: F.mono, fontSize: 9, color: C.textMuted }}>{k}</span>
                  </div>
                  {typeof v === "object" && v !== null && !isEmpty ? (
                    <pre
                      style={{
                        margin: 0,
                        fontSize: 11,
                        fontFamily: F.mono,
                        color: C.textMid,
                        whiteSpace: "pre-wrap",
                        background: C.surfaceAlt,
                        padding: "8px 12px",
                        borderRadius: 6,
                        flex: 1,
                        border: `1px solid ${C.border}`,
                      }}
                    >
                      {displayVal}
                    </pre>
                  ) : (
                    <span
                      style={{
                        fontSize: 12,
                        fontFamily: F.mono,
                        color: isEmpty ? C.textMuted : C.text,
                        fontStyle: isEmpty ? "italic" : "normal",
                        wordBreak: "break-all",
                        flex: 1,
                        marginTop: 1,
                      }}
                    >
                      {String(displayVal)}
                    </span>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// NAV COMPONENTS — defined at module scope so React never unmounts them on
// Explorer re-renders (defining components inside render recreates their
// identity every render, forcing React to unmount/remount).
// ══════════════════════════════════════════════════════════════════════════════

interface NavEntryButtonProps {
  isActive: boolean;
  navCollapsed: boolean;
  title?: string;
  onClick: () => void;
  children: React.ReactNode;
}
function NavEntryButton({ isActive, navCollapsed, title, onClick, children }: NavEntryButtonProps) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: navCollapsed ? 0 : 9,
        padding: navCollapsed ? "8px 0" : "8px 10px",
        justifyContent: navCollapsed ? "center" : "flex-start",
        borderRadius: 7,
        border: "none",
        cursor: "pointer",
        width: "100%",
        background: isActive ? C.accentBg : "transparent",
        borderLeft: !navCollapsed && isActive ? `2px solid ${C.accent}` : "2px solid transparent",
        transition: "all 0.12s",
        textAlign: "left",
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.background = C.surfaceAlt;
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.background = "transparent";
      }}
    >
      {children}
    </button>
  );
}

interface ActionBtnProps {
  title: string;
  label: string;
  subtitle: string;
  icon: React.ReactNode;
  iconBg: string;
  labelColor: string;
  subtitleColor: string;
  background: string;
  border: string;
  hoverBackground: string;
  hoverBorder: string;
  navCollapsed: boolean;
  onClick: () => void;
}
function ActionBtn({
  title,
  label,
  subtitle,
  icon,
  iconBg,
  labelColor,
  subtitleColor,
  background,
  border,
  hoverBackground,
  hoverBorder,
  navCollapsed,
  onClick,
}: ActionBtnProps) {
  return (
    <button
      type="button"
      title={navCollapsed ? title : undefined}
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: navCollapsed ? 0 : 9,
        padding: navCollapsed ? "8px 0" : "9px 10px",
        justifyContent: navCollapsed ? "center" : "flex-start",
        width: "100%",
        borderRadius: 7,
        cursor: "pointer",
        background,
        border: `1.5px solid ${border}`,
        transition: "all 0.15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = hoverBackground;
        e.currentTarget.style.borderColor = hoverBorder;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = background;
        e.currentTarget.style.borderColor = border;
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: 6,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: iconBg,
          border: "none",
        }}
      >
        <span style={{ display: "flex", color: "#fff" }}>{icon}</span>
      </div>
      {!navCollapsed && (
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 13,
              fontFamily: F.sans,
              fontWeight: 700,
              color: labelColor,
              whiteSpace: "nowrap",
            }}
          >
            {label}
          </div>
          <div style={{ fontSize: 10, color: subtitleColor, fontFamily: F.sans, marginTop: 1 }}>
            {subtitle}
          </div>
        </div>
      )}
    </button>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// EXPLORER — shell with left nav
// ══════════════════════════════════════════════════════════════════════════════
interface ExplorerProps {
  onBack: () => void;
}
function Explorer({ onBack }: ExplorerProps) {
  const [ree, setRee] = useState<Ree>(DEMO_REE);
  const [locked, setLocked] = useState(false);
  const [repoMode, setRepoMode] = useState("url");
  const [actionStates, setActionStates] = useState<ActionStates>({});
  const [badges, setBadges] = useState<Badges>({});
  const [timestamps, setTimestamps] = useState<Timestamps>({});
  const [serviceLogs, setServiceLogs] = useState<ServiceLogs>({});
  const [serviceParams, setServiceParams] = useState<ServiceParams>(() => initialServiceParams());
  const [toast, setToast] = useState<ToastState | null>(null);
  const [page, setPage] = useState<ExplorerPage>(PAGE.SOURCE); // see PAGE constant for valid values
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [virtualFiles, setVirtualFiles] = useState<FileTreeNode[]>([]);
  const [immutableSourceSnapshotFiles, setImmutableSourceSnapshotFiles] = useState<FileTreeNode[]>(
    [],
  );
  const [immutableSourceSnapshotArchiveName, setImmutableSourceSnapshotArchiveName] = useState("");

  const [showReviewerPreview, setShowReviewerPreview] = useState(false);

  const currentReeArchiveEntries = useMemo(
    () =>
      buildCurrentReeArchiveEntries(
        ree,
        virtualFiles,
        immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName,
      ),
    [ree, virtualFiles, immutableSourceSnapshotFiles, immutableSourceSnapshotArchiveName],
  );
  const currentReeFiles = useMemo(
    () => reeArchiveEntriesToFiles(currentReeArchiveEntries),
    [currentReeArchiveEntries],
  );

  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    setToast({ message: msg, type });
  const level = ree._evalLevel ?? 0; // only set by running Evaluate

  const handleSeal = () => {
    const sealHash =
      "sha256:" +
      Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
    setRee((r) => ({ ...r, _sealedAt: new Date().toISOString(), _sealHash: sealHash }));
    setLocked(true);
    showToast("REE sealed — now read-only", "success");
  };

  const handleDownloadRee = () => {
    const blob = buildZipBlob(currentReeArchiveEntries);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(ree.name || "ree").replace(/[^a-z0-9_-]/gi, "_")}-capsule.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${ree.name || "ree"}-capsule.zip`, "success");
  };

  // Reset all derived/workflow state when source in workspace changes
  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    setBadges({});
    setTimestamps({});
    setServiceLogs({});
    setActionStates({});
    setServiceParams(initialServiceParams());
    setRee((r) => ({
      ...r,
      build_runtime_script: "",
      activation_script: "",
      sbom: "",
      swhid: "",
      detected_dependencies: "",
      repro_level: "",
      _evalLevel: 0,
      _sourceAvailable: false,
      _sourceAcquiredBy: undefined,
      zenodo_doi: "",
      _uploadedArchive: "",
      _sourceSnapshotArchive: "",
      _sourceSnapshotCapturedAt: "",
    }));
    setVirtualFiles([]);
    setImmutableSourceSnapshotFiles([]);
    setImmutableSourceSnapshotArchiveName("");
    if (!options.silent) {
      showToast("Source changed — workflow status and scripts reset", "info");
    }
  };

  const handleDownloadSourceFiles = async (originType: Ree["source_type"]) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "upload") {
      showToast(
        "Source already provided via tarball upload. Change source to switch method.",
        "error",
      );
      return;
    }
    if (!ree.origin_url || !originType) {
      showToast("Set origin URL and origin type first", "error");
      return;
    }
    handleSourceChange({ silent: true });
    setActionStates((s) => ({ ...s, source: "loading" }));
    await new Promise((r) => setTimeout(r, 1400));
    setActionStates((s) => ({ ...s, source: "done" }));
    setBadges((b) => ({ ...b, source: true }));
    const ts = new Date().toISOString();
    setTimestamps((t) => ({ ...t, source: ts }));
    const workspaceFiles = makeWorkspaceFromOrigin(ree.origin_url, originType);
    const snapshotFiles = cloneTree(workspaceFiles);
    const repoBase =
      (ree.origin_url.split("/").filter(Boolean).pop() || "source").replace(
        /\.(git|tar\.gz|tgz|zip)$/i,
        "",
      ) || "source";
    const snapshotArchiveName = normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);
    setVirtualFiles(workspaceFiles);
    setImmutableSourceSnapshotFiles(snapshotFiles);
    setImmutableSourceSnapshotArchiveName(snapshotArchiveName);
    setRee((r) => ({
      ...r,
      source_type: originType,
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "",
      _sourceSnapshotArchive: snapshotArchiveName,
      _sourceSnapshotCapturedAt: ts,
    }));
    showToast(
      originType === "tarball"
        ? "Tarball downloaded and extracted into workspace"
        : "Source files downloaded into workspace",
      "success",
    );
  };

  const handleWorkspaceUpload = (payload: SourceUploadCommit) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "download") {
      showToast(
        "Source already provided via origin download. Change source to switch method.",
        "error",
      );
      return;
    }
    handleSourceChange({ silent: true });
    const ts = new Date().toISOString();

    const archiveName = payload.archiveName || "source.tar.gz";
    const workspaceFiles = makeWorkspaceFromArchiveUpload(archiveName);
    const snapshotFiles = cloneTree(workspaceFiles);
    const snapshotArchiveName = normalizeSnapshotArchiveName(archiveName);
    setVirtualFiles(workspaceFiles);
    setImmutableSourceSnapshotFiles(snapshotFiles);
    setImmutableSourceSnapshotArchiveName(snapshotArchiveName);
    setRee((r) => ({
      ...r,
      _uploadedArchive: archiveName,
      source_type: "",
      _sourceAvailable: true,
      _sourceAcquiredBy: "upload",
      _sourceSnapshotArchive: snapshotArchiveName,
      _sourceSnapshotCapturedAt: ts,
    }));
    setBadges((b) => ({ ...b, source: true }));
    setTimestamps((t) => ({ ...t, source: ts }));
    showToast("Archive extracted into workspace", "success");
  };

  const handleRemoveWorkspaceSource = () => {
    handleSourceChange({ silent: true });
    showToast("Source files removed from workspace — choose download or upload again", "info");
  };

  const runAction = async (key: string, params: Record<string, unknown> = {}) => {
    setActionStates((s) => ({ ...s, [key]: "loading" }));
    await new Promise((r) => setTimeout(r, 1600 + Math.random() * 700));

    const newLevel = key === "evaluate" ? Math.min(7, level + 1) : level;
    const lines = makeLogs(key, ree, params, newLevel);
    const ts = new Date().toISOString();

    setServiceLogs((l) => ({ ...l, [key]: { lines, ts } }));
    setActionStates((s) => ({ ...s, [key]: "done" }));
    setBadges((b) => ({ ...b, [key]: true }));
    setTimestamps((t) => ({ ...t, [key]: ts }));

    if (key === "create") {
      setLocked(true);
      showToast("REE created — fields locked", "success");
    } else if (key === "build") {
      // Produce mock output matching the declared runtime target.
      // If the caller provided an _expectedOutput param we record that as the produced runtime automatically.
      const runtimeTarget = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
      const expectedOutput = String(
        params && params._expectedOutput ? params._expectedOutput : "",
      ).trim();
      const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";
      const isTarball = /\.(tar\.gz|tgz)$/i.test(producedName);
      let producedRuntimePath: string | null = null;
      if (isTarball) {
        const mockRuntime: FileTreeNode = {
          id: "vf-runtime",
          name: producedName,
          type: "file",
          tag: "runtime",
          content: `[mock binary — docker save | gzip output]\nBuilt: ${new Date().toISOString()}\nSize: ~1.2 GB (mock)`,
        };
        setVirtualFiles((f) => [...f.filter((n) => n.name !== producedName), mockRuntime]);
        producedRuntimePath = producedName;
      }
      // Auto-set runtime only when the expected output file is actually produced.
      if (expectedOutput && producedRuntimePath && producedRuntimePath === expectedOutput) {
        setRee((r) => ({ ...r, runtime: expectedOutput, _runtimeIncluded: true }));
      } else if (expectedOutput && !producedRuntimePath) {
        showToast(
          `Build finished, but expected runtime file was not produced: ${expectedOutput}`,
          "error",
        );
      }
      showToast(`Build complete${producedName ? ` — ${producedName} produced` : ""}`, "success");
    } else if (key === "sbom") {
      // Produce mock sbom.spdx.json
      const sbomContent = JSON.stringify(
        {
          spdxVersion: "SPDX-2.3",
          dataLicense: "CC0-1.0",
          SPDXID: "SPDXRef-DOCUMENT",
          name: `${ree.name || "ree"}-sbom`,
          documentNamespace: `https://example.org/sbom/${ree.name || "ree"}-${Date.now()}`,
          creationInfo: {
            created: new Date().toISOString(),
            creators: ["Tool: syft via REE Explorer"],
          },
          packages: [
            {
              SPDXID: "SPDXRef-numpy",
              name: "numpy",
              versionInfo: "1.26.4",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-pandas",
              name: "pandas",
              versionInfo: "2.2.1",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-scipy",
              name: "scipy",
              versionInfo: "1.12.0",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-biopython",
              name: "biopython",
              versionInfo: "1.83",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
          ],
        },
        null,
        2,
      );
      const fname = "sbom.spdx.json";
      setVirtualFiles((f) => [
        ...f.filter((n) => n.name !== fname),
        { id: "vf-sbom", name: fname, type: "file", tag: "sbom", content: sbomContent },
      ]);
      setRee((r) => ({ ...r, sbom: fname }));
      showToast("SBOM generated — sbom.spdx.json", "success");
    } else if (key === "activation") {
      showToast("Activation test passed — container started cleanly", "success");
    } else if (key === "evaluate") {
      const depSummary = (() => {
        const groups = scanDependencies(virtualFiles || MOCK_FILES);
        const depCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
        const manifestCount = groups.length;
        return `${depCount} dependenc${depCount === 1 ? "y" : "ies"} across ${manifestCount} manifest file${manifestCount === 1 ? "" : "s"}`;
      })();
      setRee((r) => ({
        ...r,
        _evalLevel: newLevel,
        repro_level: `L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`,
        detected_dependencies: depSummary,
      }));
      showToast(`L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`, "success");
    } else if (key === "swh") {
      const swhid = `swh:1:dir:${Math.random().toString(16).slice(2, 14)}`;
      setRee((r) => ({ ...r, swhid }));
      showToast("Archived at Software Heritage — SWHID assigned", "success");
    } else if (key === "zenodo") {
      const doi = `10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`;
      setRee((r) => ({ ...r, zenodo_doi: doi }));
      showToast("Published on Zenodo — DOI assigned", "success");
    } else if (key === "dataverse") {
      const doi = `doi:10.5072/DVN/${Math.floor(Math.random() * 900000 + 100000)}`;
      setRee((r) => ({ ...r, dataverse_doi: doi }));
      showToast("Dataset published on Dataverse — DOI assigned", "success");
    } else {
      const svc = [EVALUATE_SVC, ...SERVICES].find((s) => s.key === key);
      showToast(`${svc.label} completed`, "success");
    }
  };

  // ── Workflow steps ─────────────────────────────────────────────────────────────
  const WORKFLOW_STEPS = [
    {
      n: 1,
      key: PAGE.SOURCE,
      label: "Source Repo",
      IC: Ic.globe,
      svc: null,
      desc: "Set origin, type, and download source files",
    },
    {
      n: 2,
      key: PAGE.METADATA,
      label: "Provide Metadata",
      IC: Ic.grid,
      svc: null,
      desc: "Input metadata about the project",
    },
    {
      n: 3,
      key: PAGE.EVALUATE,
      label: "Evaluate",
      IC: EVALUATE_SVC.IC,
      svc: EVALUATE_SVC,
      desc: "Score reproducibility level",
    },
    {
      n: 4,
      key: PAGE.BUILD,
      label: "Build Runtime",
      IC: Ic.cpu,
      svc: SERVICES.find((s) => s.key === PAGE.BUILD),
      desc: "Build the runtime tarball",
    },
    {
      n: 5,
      key: PAGE.SBOM,
      label: "Generate SBOM",
      IC: Ic.package,
      svc: SERVICES.find((s) => s.key === PAGE.SBOM),
      desc: "Scan runtime with syft",
    },
    {
      n: 6,
      key: PAGE.ACTIVATION,
      label: "Test Activation",
      IC: Ic.shield,
      svc: SERVICES.find((s) => s.key === PAGE.ACTIVATION),
      desc: "Verify container activates",
    },
    {
      n: 7,
      key: PAGE.ARCHIVE,
      label: "Deposit & Share",
      IC: Ic.globe,
      svc: null,
      desc: "Archive and publish",
    },
    { n: 8, key: PAGE.SEAL, label: "Seal", IC: Ic.lock, svc: null, desc: "Seal the REE" },
  ];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      {/* Top bar */}
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = C.textMid;
            e.currentTarget.style.background = C.surfaceAlt;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = C.textMuted;
            e.currentTarget.style.background = "none";
          }}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Explorer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
      </header>

      {/* Body: nav + content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        {/* Left nav — collapsible: full labels or icons-only */}
        <nav
          style={{
            width: navCollapsed ? 52 : 200,
            borderRight: `1px solid ${C.border}`,
            background: C.surface,
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            overflowX: "hidden",
            flexShrink: 0,
            minHeight: 0,
            transition: "width 0.2s cubic-bezier(0.4,0,0.2,1)",
          }}
        >
          {/* iconBtn: render helper (not a component — holds no state, safe to define inline) */}
          {((): React.ReactNode => {
            const iconBtn = (
              key: string,
              icon: React.ReactNode,
              label: string,
              subtitle?: string | null,
            ) => {
              const isActive = page === key;
              return (
                <NavEntryButton
                  title={navCollapsed ? label : undefined}
                  onClick={() => setPage(key as ExplorerPage)}
                  isActive={isActive}
                  navCollapsed={navCollapsed}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: isActive ? C.accent : C.surfaceAlt,
                      border: isActive ? "none" : `1.5px solid ${C.border}`,
                    }}
                  >
                    <span style={{ display: "flex", color: isActive ? "#fff" : C.textMuted }}>
                      {icon}
                    </span>
                  </div>
                  {!navCollapsed && (
                    <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontFamily: F.sans,
                          fontWeight: 600,
                          color: isActive ? C.accent : C.textMid,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {label}
                      </div>
                      {subtitle && (
                        <div
                          style={{
                            fontSize: 10,
                            color: C.textMuted,
                            fontFamily: F.sans,
                            marginTop: 1,
                          }}
                        >
                          {subtitle}
                        </div>
                      )}
                    </div>
                  )}
                </NavEntryButton>
              );
            };

            return (
              <>
                {/* Top toggle button */}
                <div
                  style={{
                    padding: "6px 8px",
                    borderBottom: `1px solid ${C.border}`,
                    display: "flex",
                    justifyContent: navCollapsed ? "center" : "flex-start",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setNavCollapsed((c) => !c)}
                    title={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 30,
                      height: 30,
                      borderRadius: 6,
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      color: C.textMuted,
                      transition: "all 0.12s",
                      flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = C.surfaceAlt;
                      e.currentTarget.style.color = C.textMid;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                      e.currentTarget.style.color = C.textMuted;
                    }}
                  >
                    {Ic.menu(15)}
                  </button>
                </div>

                {/* Overview + Browse Files */}
                <div
                  style={{
                    padding: navCollapsed ? "8px 6px 4px" : "8px 8px 4px",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  {iconBtn("overview", Ic.layers(12), "Overview", "pod · level · state")}
                </div>
                <div
                  style={{
                    padding: navCollapsed ? "4px 6px 8px" : "4px 8px 8px",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  {iconBtn("files", Ic.files(12), "Browse Files", null)}
                </div>

                {/* Workflow label */}
                {!navCollapsed && (
                  <div style={{ padding: "10px 14px 4px" }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        letterSpacing: 1.3,
                        color: C.textMuted,
                        textTransform: "uppercase",
                        fontFamily: F.sans,
                      }}
                    >
                      Workflow
                    </span>
                  </div>
                )}
                {navCollapsed && <div style={{ height: 8 }} />}

                {/* Numbered steps */}
                <div
                  style={{
                    padding: navCollapsed ? "0 6px" : "0 8px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 1,
                    flex: 1,
                  }}
                >
                  {WORKFLOW_STEPS.map((step, i) => {
                    const isActive = page === step.key;
                    const svc = step.svc;
                    let hasRun = false;
                    if (step.key === PAGE.SOURCE) hasRun = !!ree._sourceAvailable;
                    else if (step.key === PAGE.METADATA) hasRun = !!ree.name;
                    else if (step.key === PAGE.SEAL) hasRun = !!ree._sealedAt;
                    else if (step.key === PAGE.ARCHIVE)
                      hasRun = !!badges["swh"] || !!badges["zenodo"] || !!badges["dataverse"];
                    else hasRun = !!badges[step.key];
                    const running = svc && actionStates[step.key] === "loading";
                    const ts = timestamps[step.key];
                    const tsShort = ts
                      ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                      : null;
                    const isLast = i === WORKFLOW_STEPS.length - 1;

                    return (
                      <div key={step.key} style={{ display: "flex", flexDirection: "column" }}>
                        <NavEntryButton
                          title={
                            navCollapsed
                              ? `${step.n}. ${step.label}${tsShort ? ` — last run ${tsShort}` : ""}`
                              : undefined
                          }
                          onClick={() => setPage(step.key as ExplorerPage)}
                          isActive={isActive}
                          navCollapsed={navCollapsed}
                        >
                          {/* Step bubble */}
                          <div
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: "50%",
                              flexShrink: 0,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              background: isActive ? C.accent : C.surfaceAlt,
                              border: isActive
                                ? "none"
                                : `1.5px solid ${hasRun ? C.accentBorder : C.border}`,
                              position: "relative",
                              transition: "all 0.2s",
                            }}
                          >
                            {running ? (
                              <span
                                style={{
                                  display: "flex",
                                  color: C.accent,
                                  animation: "spin 0.9s linear infinite",
                                }}
                              >
                                {Ic.loader(11)}
                              </span>
                            ) : (
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  fontFamily: F.mono,
                                  color: isActive ? "#fff" : C.textMuted,
                                }}
                              >
                                {step.n}
                              </span>
                            )}
                            {hasRun && !running && !isActive && (
                              <div
                                style={{
                                  position: "absolute",
                                  bottom: -1,
                                  right: -1,
                                  width: 8,
                                  height: 8,
                                  borderRadius: "50%",
                                  background: C.accent,
                                  border: `1.5px solid ${C.surface}`,
                                }}
                              />
                            )}
                          </div>

                          {/* Label — hidden when collapsed */}
                          {!navCollapsed && (
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div
                                style={{
                                  fontSize: 13,
                                  fontFamily: F.sans,
                                  fontWeight: isActive ? 600 : 400,
                                  color: isActive ? C.accent : C.textMid,
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  lineHeight: 1.3,
                                }}
                              >
                                {step.label}
                              </div>
                              <div
                                style={{
                                  fontSize: 10,
                                  color: C.textMuted,
                                  fontFamily: F.mono,
                                  marginTop: 1,
                                }}
                              >
                                {running ? "running…" : tsShort ? `last run ${tsShort}` : step.desc}
                              </div>
                            </div>
                          )}
                        </NavEntryButton>

                        {!isLast && (
                          <div
                            style={{
                              marginLeft: navCollapsed ? 14 : 19,
                              width: 2,
                              height: 6,
                              background: C.border,
                              borderRadius: 99,
                              marginTop: 1,
                              marginBottom: 1,
                            }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Download and Preview button — pinned to nav bottom */}
                <div
                  style={{
                    marginTop: "auto",
                    padding: navCollapsed ? "8px 6px" : "8px 8px",
                    borderTop: `1px solid ${C.border}`,
                  }}
                >
                  {/* Download button — always available (even if not sealed) */}
                  <div style={{ marginBottom: 8 }}>
                    <ActionBtn
                      title="Download REE"
                      label="Download REE"
                      subtitle="export capsule.zip"
                      icon={Ic.download(11)}
                      iconBg="#2563eb"
                      labelColor="#1e3a8a"
                      subtitleColor={C.textMuted}
                      background="#eef6ff"
                      border="#dbeafe"
                      hoverBackground="#e0f2ff"
                      hoverBorder="#93c5fd"
                      navCollapsed={navCollapsed}
                      onClick={handleDownloadRee}
                    />
                  </div>
                  {/* Preview button — always available (even if not sealed) */}
                  <ActionBtn
                    title="Preview as Reviewer"
                    label="Preview"
                    subtitle="reviewer's view"
                    icon={Ic.star(11)}
                    iconBg="#f59e0b"
                    labelColor="#92400e"
                    subtitleColor="#b45309"
                    background="#fef3c7"
                    border="#fde68a"
                    hoverBackground="#fef08a40"
                    hoverBorder="#f59e0b"
                    navCollapsed={navCollapsed}
                    onClick={() => setShowReviewerPreview(true)}
                  />
                </div>
              </>
            );
          })()}
        </nav>

        {/* Main content */}
        <main
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            minWidth: 0,
            position: "relative",
            background:
              "linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 35%, #fff5f9 65%, #f4f8ff 100%)",
          }}
        >
          {/* Gradient blobs that the frosted glass blurs */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              zIndex: 0,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                width: 480,
                height: 320,
                borderRadius: "50%",
                top: -80,
                left: "10%",
                background: "radial-gradient(ellipse, #c7d9ff88 0%, transparent 70%)",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 360,
                height: 280,
                borderRadius: "50%",
                top: 20,
                right: "5%",
                background: "radial-gradient(ellipse, #e0d0ff66 0%, transparent 70%)",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 300,
                height: 200,
                borderRadius: "50%",
                top: 160,
                left: "35%",
                background: "radial-gradient(ellipse, #ffd6e855 0%, transparent 70%)",
              }}
            />
          </div>
          <div
            style={{
              position: "relative",
              zIndex: 1,
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              minWidth: 0,
            }}
          >
            {(page === PAGE.OVERVIEW || page === PAGE.SEAL) && (
              <div
                style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}
              >
                <PageOverview
                  ree={ree}
                  onReeChange={setRee}
                  level={level}
                  onNavigate={(key) => setPage(key as ExplorerPage)}
                  badges={badges}
                  timestamps={timestamps}
                  onGoField={(key) => {
                    setPage(FIELD_TO_PAGE[String(key)] || PAGE.METADATA);
                    setFocusedField(key);
                  }}
                  files={virtualFiles}
                  snapshotFiles={immutableSourceSnapshotFiles}
                  locked={locked}
                  onSeal={handleSeal}
                  onPreviewReviewer={() => setShowReviewerPreview(true)}
                  onDownloadRee={ree._sealedAt ? handleDownloadRee : undefined}
                />
              </div>
            )}
            {page === PAGE.SOURCE && (
              <PageSourceRepoEntry
                ree={ree}
                onChange={setRee}
                locked={locked}
                repoMode={repoMode}
                onRepoModeChange={setRepoMode}
                onSourceChange={handleSourceChange}
                badges={badges}
                onDownloadSource={(originType) => handleDownloadSourceFiles(originType)}
                onWorkspaceUpload={handleWorkspaceUpload}
                onRemoveWorkspaceSource={handleRemoveWorkspaceSource}
                downloadRunning={actionStates["source"] === "loading"}
                downloadDone={!!ree._sourceAvailable}
                onGoService={(key) => setPage(key as ExplorerPage)}
                focusedField={focusedField}
                setFocusedField={setFocusedField}
              />
            )}
            {page === PAGE.METADATA && (
              <PageMetadataEntry
                ree={ree}
                onChange={setRee}
                locked={locked}
                setLocked={setLocked}
                badges={badges}
                onGoService={(key) => setPage(key as ExplorerPage)}
                focusedField={focusedField}
                setFocusedField={setFocusedField}
              />
            )}
            {[EVALUATE_SVC, ...SERVICES].map((svc) => {
              if (page !== svc.key) return null;
              const ServicePageComponent = SERVICE_PAGE_COMPONENTS[svc.key];
              if (!ServicePageComponent) return null;
              const params = serviceParams[svc.key] ?? defaultParamsForService(svc);
              const setParam = (paramKey: string, value: unknown) => {
                setServiceParams((prev) => ({
                  ...prev,
                  [svc.key]: {
                    ...(prev[svc.key] ?? defaultParamsForService(svc)),
                    [paramKey]: value,
                  },
                }));
              };

              return (
                <div
                  key={svc.key}
                  style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
                >
                  <ServicePageComponent
                    svc={svc}
                    ree={ree}
                    log={serviceLogs[svc.key]}
                    running={actionStates[svc.key] === "loading"}
                    runDone={!!badges[svc.key]}
                    badge={badges[svc.key] ? svc.badge : null}
                    ts={timestamps[svc.key]}
                    onRun={runAction}
                    onGoFields={() => {
                      const sourceFieldKeys: (keyof Ree)[] = [
                        "origin_url",
                        "source_type",
                        "_sourceAvailable",
                      ];
                      const hasSourceGap = missingRequirements(svc, ree).some((req) =>
                        sourceFieldKeys.includes(req.field),
                      );
                      setPage(hasSourceGap ? PAGE.SOURCE : PAGE.METADATA);
                    }}
                    badges={badges}
                    onGo={(key) => setPage(key as ExplorerPage)}
                    files={virtualFiles}
                    onFilesChange={setVirtualFiles}
                    onReeChange={setRee}
                    missing={missingRequirements(svc, ree)}
                    params={params}
                    setParam={setParam}
                  />
                </div>
              );
            })}
            {page === PAGE.ARCHIVE && (
              <div style={{ flex: 1, overflowY: "auto" }}>
                <PageArchive
                  ree={ree}
                  badges={badges}
                  logs={serviceLogs}
                  actionStates={actionStates}
                  onRun={runAction}
                  onGo={(key) => setPage(key as ExplorerPage)}
                />
              </div>
            )}
            {page === PAGE.FILES && (
              <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
                <PageFiles files={virtualFiles} reeFiles={currentReeFiles} />
              </div>
            )}
          </div>
        </main>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── Reviewer Preview Overlay ── */}
      {showReviewerPreview && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Thin dismiss bar at top */}
          <div
            style={{
              height: 40,
              background: "#0f172a",
              borderBottom: "1px solid #1e293b",
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0 16px",
              flexShrink: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#f59e0b",
                  boxShadow: "0 0 6px #f59e0b80",
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: 1.2,
                  color: "#94a3b8",
                  fontFamily: F.sans,
                  textTransform: "uppercase",
                }}
              >
                Reviewer Preview
              </span>
            </div>
            <span style={{ fontSize: 11, color: "#475569", fontFamily: F.sans }}>
              — this is how a reviewer will see your sealed REE
            </span>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              onClick={() => setShowReviewerPreview(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 12px",
                borderRadius: 6,
                border: "1px solid #334155",
                background: "#1e293b",
                color: "#94a3b8",
                cursor: "pointer",
                fontSize: 12,
                fontFamily: F.sans,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#334155";
                e.currentTarget.style.color = "#e2e8f0";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#1e293b";
                e.currentTarget.style.color = "#94a3b8";
              }}
            >
              {Ic.x(12)} Exit Preview
            </button>
          </div>
          {/* Full ReviewerView below the bar */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <ReviewerView ree={ree} onBack={() => setShowReviewerPreview(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Landing ────────────────────────────────────────────────────────────────────
interface LandingProps {
  onLoad: (page?: AppPage) => void;
}
function Landing({ onLoad }: LandingProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const go = async () => {
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setLoading(false);
    onLoad();
  };
  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 430, width: "100%", animation: "fadeUp 0.4s ease" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 50,
              height: 50,
              borderRadius: 13,
              background: C.accentBg,
              border: `1px solid ${C.accentBorder}`,
              color: C.accent,
              marginBottom: 14,
            }}
          >
            {Ic.layers(22)}
          </div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              color: C.text,
              letterSpacing: -0.5,
              marginBottom: 6,
            }}
          >
            REE Explorer
          </h1>
          <p style={{ fontSize: 14, color: C.textMid, lineHeight: 1.6 }}>
            Build, inspect, and certify
            <br />
            Reproducible Execution Environments
          </p>
        </div>
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            padding: 22,
            boxShadow: "0 2px 12px rgba(0,0,0,0.05)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <label
            style={{
              fontSize: 11,
              letterSpacing: 1.4,
              color: C.textMuted,
              fontFamily: F.sans,
              textTransform: "uppercase",
            }}
          >
            Repository URL
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  left: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: C.textMuted,
                }}
              >
                {Ic.link()}
              </div>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && url.trim() && go()}
                placeholder="https://github.com/org/repo"
                style={{
                  width: "100%",
                  border: `1.5px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 10px 8px 32px",
                  fontSize: 14,
                  fontFamily: F.mono,
                  color: C.text,
                  background: C.bg,
                }}
              />
            </div>
            <button
              type="button"
              onClick={go}
              disabled={loading}
              style={{
                background: C.accent,
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "8px 16px",
                cursor: "pointer",
                fontSize: 14,
                fontWeight: 600,
                fontFamily: F.sans,
                display: "flex",
                alignItems: "center",
                gap: 5,
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  display: "flex",
                  animation: loading ? "spin 0.9s linear infinite" : "none",
                }}
              >
                {loading ? Ic.loader() : Ic.play()}
              </span>
              {loading ? "…" : "Load"}
            </button>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1, height: 1, background: C.border }} />
            <span style={{ fontSize: 12, color: C.textMuted, fontFamily: F.mono }}>or</span>
            <div style={{ flex: 1, height: 1, background: C.border }} />
          </div>
          <input
            ref={fileRef}
            type="file"
            style={{ display: "none" }}
            onChange={(e) => {
              if (e.target.files?.[0]) go();
            }}
            accept=".zip,.tar,.tar.gz"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            style={{
              background: C.bg,
              border: `1.5px dashed ${C.borderMid}`,
              borderRadius: 10,
              padding: 16,
              cursor: "pointer",
              width: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 5,
              transition: "border-color 0.15s, background 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = C.accent;
              e.currentTarget.style.background = C.accentBg;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = C.borderMid;
              e.currentTarget.style.background = C.bg;
            }}
          >
            <span style={{ color: C.accent }}>{Ic.upload()}</span>
            <span style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans }}>
              Drop archive or <span style={{ color: C.accent }}>browse</span>
            </span>
            <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono }}>
              .zip · .tar · .tar.gz
            </span>
          </button>
          <button
            type="button"
            onClick={() => onLoad(APP_PAGE.EXPLORER)}
            disabled={loading}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: 8,
              cursor: "pointer",
              width: "100%",
              fontSize: 13,
              color: C.textMid,
              fontFamily: F.sans,
              transition: "background 0.13s, color 0.13s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = C.surfaceAlt;
              e.currentTarget.style.color = C.text;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = C.textMid;
            }}
          >
            ✦ Try with demo repository (Author)
          </button>
          <button
            type="button"
            onClick={() => onLoad(APP_PAGE.REVIEWER)}
            disabled={loading}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: 8,
              cursor: "pointer",
              width: "100%",
              fontSize: 13,
              color: C.textMid,
              fontFamily: F.sans,
              transition: "background 0.13s, color 0.13s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = C.surfaceAlt;
              e.currentTarget.style.color = C.text;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = C.textMid;
            }}
          >
            ✦ Review a sealed pod (Reviewer)
          </button>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 12,
            marginTop: 20,
            flexWrap: "wrap",
          }}
        >
          {LEVELS.map((l) => (
            <div
              key={l.n}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: l.color }} />L
              {l.n} {l.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// REVIEWER EXPLORER — Read-only verification view
// ══════════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════════
// REVIEWER VIEW
// ══════════════════════════════════════════════════════════════════════════════

// ── Reactivation step definitions ─────────────────────────────────────────────
interface ReactivationStep {
  key: string;
  label: string;
  icon: (s?: number) => JSX.Element;
  color: string;
  desc: string;
  params?: ServiceParam[];
  logLines: (ree: Ree, params?: Record<string, unknown>) => LogLine[];
}

const REACTIVATION_STEPS: ReactivationStep[] = [
  {
    key: "fetch",
    label: "Fetch Archive",
    icon: Ic.archive,
    color: "#0891b2",
    desc: "Download the sealed REE archive from Software Heritage or Zenodo.",
    logLines: (ree) => [
      { type: "info", msg: "Fetching REE archive from registry…" },
      { type: "info", msg: `  SWHID: ${ree.swhid || "(not set)"}` },
      { type: "info", msg: `  DOI:   ${ree.zenodo_doi || "(not set)"}` },
      { type: "info", msg: "Verifying archive checksum…" },
      { type: "ok", msg: "SHA-256 matches manifest ✓" },
      { type: "ok", msg: `Archive fetched — ${ree.name}.ree.tar.gz (1.4 GB)` },
    ],
  },
  {
    key: "rebuild",
    label: "Rebuild Runtime",
    icon: Ic.cpu,
    color: "#7c3aed",
    desc: "Execute the build script from scratch with --no-cache to reconstruct the container image.",
    params: [
      {
        key: "no_cache",
        label: "No cache",
        type: "bool",
        default: true,
        hint: "Pass --no-cache to docker build",
      },
      {
        key: "platform",
        label: "Platform",
        type: "select",
        default: "linux/amd64",
        options: ["linux/amd64", "linux/arm64"],
        hint: "Target platform",
      },
    ],
    logLines: (ree, params) => [
      { type: "info", msg: `Platform: ${params?.platform || "linux/amd64"}` },
      { type: "info", msg: `No-cache: ${params?.no_cache !== false ? "yes" : "no"}` },
      { type: "info", msg: `Running: bash ${ree.build_runtime_script}` },
      { type: "info", msg: "DOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest ." },
      { type: "info", msg: "[1/6] FROM python:3.11.7-slim-bookworm" },
      { type: "info", msg: "[2/6] WORKDIR /app" },
      { type: "info", msg: "[3/6] COPY . ." },
      { type: "info", msg: "[4/6] RUN pip install --no-cache-dir -r requirements.txt" },
      { type: "info", msg: "  numpy==1.26.4 … installed" },
      { type: "info", msg: "  pandas==2.2.1 … installed" },
      { type: "info", msg: "  scipy==1.12.0 … installed" },
      { type: "info", msg: '[5/6] CMD ["python", "src/main.py"]' },
      { type: "info", msg: "Saving image as runtime.tar.gz …" },
      { type: "ok", msg: "Build complete — runtime.tar.gz produced (1.2 GB)" },
    ],
  },
  {
    key: "diffcheck",
    label: "Diff Check",
    icon: Ic.refresh,
    color: "#b45309",
    desc: "Compare the rebuilt image digest against the sealed artifact's manifest hash.",
    logLines: () => [
      { type: "info", msg: "Digesting sealed runtime.tar.gz …" },
      {
        type: "info",
        msg: "  Original: sha256:4a8f2e1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f",
      },
      { type: "info", msg: "Digesting rebuilt runtime.tar.gz …" },
      {
        type: "info",
        msg: "  Rebuilt:  sha256:4a8f2e1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f2a1c3b9d6e7f",
      },
      { type: "ok", msg: "Digests match — environment is byte-for-byte reproducible ✓" },
      { type: "info", msg: "SBOM component diff: 0 additions, 0 removals" },
      { type: "ok", msg: "SBOM unchanged ✓" },
    ],
  },
  {
    key: "activate",
    label: "Activate & Verify",
    icon: Ic.shield,
    color: "#16a34a",
    desc: "Load the rebuilt runtime and run the activation script to verify the environment starts cleanly.",
    logLines: (ree) => [
      { type: "info", msg: `Running: bash ${ree.activation_script}` },
      { type: "info", msg: "docker load < runtime.tar.gz" },
      { type: "info", msg: "Loaded image: ree:latest" },
      { type: "info", msg: `docker run --rm --entrypoint="" ree:latest echo ok` },
      { type: "ok", msg: "ok" },
      { type: "ok", msg: "Activation test passed — container starts cleanly ✓" },
    ],
  },
];

// ── Animated log panel ─────────────────────────────────────────────────────────
interface ReviewLogPanelProps {
  lines: LogLine[] | null;
  running: boolean;
}
function ReviewLogPanel({ lines, running }: ReviewLogPanelProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [displayed, setDisplayed] = useState<LogLine[]>([]);

  useEffect(() => {
    if (!lines) {
      setDisplayed([]);
      return;
    }
    setDisplayed([]);
    let i = 0;
    let timer;
    let active = true;
    const tick = () => {
      if (!active || i >= lines.length) return;
      const nextLine = lines[i++];
      setDisplayed((d) => [...d, nextLine]);
      timer = setTimeout(tick, 80 + Math.random() * 60);
    };
    tick();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [lines]);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [displayed]);

  const typeColor = { ok: "#22c55e", error: "#ef4444", warn: "#f59e0b", info: "#94a3b8" };
  const typePrefix = { ok: "✓ ", error: "✗ ", warn: "⚠ ", info: "  " };

  return (
    <div
      ref={ref}
      style={{
        background: "#0d1117",
        borderRadius: 8,
        border: "1px solid #1e293b",
        minHeight: 160,
        maxHeight: 260,
        overflowY: "auto",
        padding: "12px 14px",
        fontFamily: F.mono,
        fontSize: 12,
        lineHeight: 1.8,
      }}
    >
      {displayed.length === 0 && !running && (
        <span style={{ color: "#4a5568", fontStyle: "italic" }}>Output will appear here…</span>
      )}
      {displayed.map((l, i) => (
        <div key={i} style={{ color: typeColor[l.type] || "#e2e8f0" }}>
          <span style={{ color: typeColor[l.type] || "#64748b", userSelect: "none" }}>
            {typePrefix[l.type] || "  "}
          </span>
          {l.msg}
        </div>
      ))}
      {running && (
        <div
          style={{ color: "#64748b", display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}
        >
          <span style={{ animation: "spin 0.9s linear infinite", display: "inline-flex" }}>
            {Ic.loader(11)}
          </span>
          <span>running…</span>
        </div>
      )}
    </div>
  );
}

// ── Metadata field row ─────────────────────────────────────────────────────────
interface MetaRowProps {
  label: string;
  value?: string;
  mono?: boolean;
  href?: string;
  color?: string;
}
function MetaRow({ label, value, mono = false, href, color }: MetaRowProps) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    if (!value) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };
  if (!value)
    return (
      <div
        style={{
          display: "flex",
          gap: 10,
          padding: "7px 0",
          borderBottom: `1px solid ${C.border}`,
          alignItems: "center",
        }}
      >
        <span
          style={{
            width: 130,
            fontSize: 11,
            color: C.textMuted,
            fontFamily: F.sans,
            flexShrink: 0,
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMuted, fontStyle: "italic" }}>
          not set
        </span>
      </div>
    );
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "7px 0",
        borderBottom: `1px solid ${C.border}`,
        alignItems: "center",
      }}
    >
      <span
        style={{
          width: 130,
          fontSize: 11,
          color: C.textMuted,
          fontFamily: F.sans,
          flexShrink: 0,
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span
        style={{
          flex: 1,
          fontSize: 11,
          fontFamily: mono ? F.mono : F.sans,
          color: color || (mono ? C.accent : C.text),
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            style={{
              color: C.accent,
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              textDecoration: "none",
            }}
          >
            {value} {Ic.externalLink(10)}
          </a>
        ) : (
          value
        )}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy"
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: copied ? "#22c55e" : C.textMuted,
          display: "flex",
          padding: 2,
          flexShrink: 0,
          borderRadius: 3,
          transition: "color 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = C.textMid)}
        onMouseLeave={(e) => (e.currentTarget.style.color = copied ? "#22c55e" : C.textMuted)}
      >
        {copied ? Ic.check(11) : Ic.copy(11)}
      </button>
    </div>
  );
}

// ── Reproducibility level badge ────────────────────────────────────────────────
interface LevelBadgeProps {
  level: number;
  large?: boolean;
}
function LevelBadge({ level, large = false }: LevelBadgeProps) {
  const lv = LEVELS[Math.min(level, 7)];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: large ? 8 : 5,
        padding: large ? "6px 12px" : "3px 8px",
        background: lv.bg,
        border: `1.5px solid ${lv.color}40`,
        borderRadius: large ? 8 : 5,
      }}
    >
      <div
        style={{
          width: large ? 8 : 6,
          height: large ? 8 : 6,
          borderRadius: "50%",
          background: lv.color,
          boxShadow: `0 0 6px ${lv.color}80`,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontSize: large ? 13 : 11,
          fontWeight: 700,
          fontFamily: F.mono,
          color: lv.color,
          letterSpacing: 0.4,
        }}
      >
        L{level} · {lv.label}
      </span>
    </div>
  );
}

// ── Step card ──────────────────────────────────────────────────────────────────
interface RvStepCardProps {
  step: ReactivationStep;
  index: number;
  state: StepState;
  log: LogLine[] | null;
  params: Record<string, unknown>;
  onSetParam: (stepKey: string, paramKey: string, value: unknown) => void;
  onRun: (key: string, params: Record<string, unknown>) => void;
  isLast: boolean;
  prevDone: boolean;
}
function RvStepCard({
  step,
  index,
  state,
  log,
  params,
  onSetParam,
  onRun,
  isLast,
  prevDone,
}: RvStepCardProps) {
  const done = state === "done";
  const running = state === "loading";
  const locked = !prevDone && !done;
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (running) setExpanded(true);
  }, [running]);

  const col = done ? "#22c55e" : locked ? C.textMuted : step.color;
  const borderCol = done ? "#22c55e40" : locked ? C.border : `${step.color}30`;
  const bgCol = done ? "#f0fdf4" : locked ? C.bg : `${step.color}08`;

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          flexShrink: 0,
          width: 28,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            flexShrink: 0,
            background: done ? "#22c55e" : locked ? C.surfaceAlt : `${step.color}18`,
            border: `2px solid ${done ? "#22c55e" : locked ? C.borderMid : step.color}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: done ? "#fff" : locked ? C.textMuted : step.color,
            transition: "all 0.3s",
            boxShadow: done
              ? "0 0 0 3px #22c55e20"
              : running
                ? `0 0 0 3px ${step.color}25`
                : "none",
          }}
        >
          {done ? (
            Ic.check(11)
          ) : (
            <span
              style={{ animation: running ? "spin 0.9s linear infinite" : "none", display: "flex" }}
            >
              {running ? Ic.loader(11) : step.icon(11)}
            </span>
          )}
        </div>
        {!isLast && (
          <div
            style={{
              flex: 1,
              width: 2,
              minHeight: 20,
              marginTop: 4,
              background: done ? "#22c55e" : C.border,
              transition: "background 0.4s",
              borderRadius: 1,
            }}
          />
        )}
      </div>
      <div
        style={{
          flex: 1,
          marginBottom: isLast ? 0 : 14,
          background: bgCol,
          border: `1.5px solid ${borderCol}`,
          borderRadius: 10,
          overflow: "hidden",
          transition: "all 0.25s",
          opacity: locked ? 0.55 : 1,
        }}
      >
        <button
          type="button"
          onClick={() => !locked && setExpanded((e) => !e)}
          disabled={locked}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 9,
            padding: "11px 14px",
            background: "transparent",
            border: "none",
            cursor: locked ? "default" : "pointer",
            textAlign: "left",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 1 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.6,
                  color: col,
                  background: `${col}15`,
                  border: `1px solid ${col}30`,
                  borderRadius: 3,
                  padding: "0 5px",
                }}
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: locked ? C.textMuted : C.text,
                  fontFamily: F.sans,
                }}
              >
                {step.label}
              </span>
              {done && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#16a34a",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 4,
                    padding: "1px 6px",
                  }}
                >
                  ✓ passed
                </span>
              )}
              {running && (
                <span
                  style={{
                    fontSize: 11,
                    color: step.color,
                    background: `${step.color}12`,
                    border: `1px solid ${step.color}30`,
                    borderRadius: 4,
                    padding: "1px 6px",
                  }}
                >
                  running…
                </span>
              )}
            </div>
            <span
              style={{ fontSize: 12, color: locked ? C.textMuted : C.textMid, fontFamily: F.sans }}
            >
              {step.desc}
            </span>
          </div>
          {!locked && (
            <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
              {expanded ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
          )}
        </button>
        {expanded && !locked && (
          <div
            style={{
              padding: "0 14px 14px",
              borderTop: `1px solid ${borderCol}`,
              background: "rgba(255,255,255,0.6)",
            }}
          >
            {step.params && step.params.length > 0 && (
              <div style={{ paddingTop: 12, marginBottom: 12 }}>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 1.2,
                    color: C.textMuted,
                    textTransform: "uppercase",
                    fontFamily: F.sans,
                    marginBottom: 10,
                  }}
                >
                  Parameters
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {step.params.map((p) => (
                    <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: C.text,
                            fontFamily: F.sans,
                          }}
                        >
                          {p.label}
                        </div>
                        <div style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</div>
                      </div>
                      {p.type === "bool" ? (
                        <button
                          type="button"
                          onClick={() => onSetParam(step.key, p.key, !params[p.key])}
                          style={{
                            width: 40,
                            height: 22,
                            borderRadius: 11,
                            border: "none",
                            cursor: "pointer",
                            background: params[p.key] ? step.color : C.borderMid,
                            position: "relative",
                            flexShrink: 0,
                            transition: "background 0.2s",
                          }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              top: 2,
                              left: params[p.key] ? 20 : 2,
                              width: 18,
                              height: 18,
                              borderRadius: "50%",
                              background: "#fff",
                              transition: "left 0.2s",
                              boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                            }}
                          />
                        </button>
                      ) : p.type === "select" ? (
                        <select
                          value={String(params[p.key] ?? "")}
                          onChange={(e) => onSetParam(step.key, p.key, e.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 6,
                            padding: "5px 8px",
                            fontSize: 13,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                            flexShrink: 0,
                          }}
                        >
                          {p.options.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => onRun(step.key, params)}
              disabled={running}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 7,
                width: "100%",
                padding: "9px 14px",
                borderRadius: 8,
                background: running ? `${step.color}20` : done ? "#f0fdf4" : step.color,
                border: done ? "1.5px solid #bbf7d0" : "none",
                color: running ? step.color : done ? "#16a34a" : "#fff",
                fontSize: 13,
                fontWeight: 600,
                fontFamily: F.sans,
                cursor: running ? "wait" : "pointer",
                transition: "all 0.15s",
                marginBottom: log ? 12 : 0,
                boxShadow: !done && !running ? `0 2px 10px ${step.color}35` : "none",
              }}
            >
              <span
                style={{
                  display: "flex",
                  animation: running ? "spin 0.9s linear infinite" : "none",
                }}
              >
                {running ? Ic.loader(13) : done ? Ic.refresh(13) : Ic.play(13)}
              </span>
              {running ? "Running…" : done ? "Re-run" : `Run ${step.label}`}
            </button>
            {log && <ReviewLogPanel lines={log} running={running} />}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Verdict banner ─────────────────────────────────────────────────────────────
interface RvVerdictBannerProps {
  allDone: boolean;
}
function RvVerdictBanner({ allDone }: RvVerdictBannerProps) {
  if (!allDone) return null;
  return (
    <div
      style={{
        background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
        border: "1.5px solid #22c55e40",
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        boxShadow: "0 0 0 4px #22c55e10, 0 4px 20px rgba(34,197,94,0.12)",
        animation: "fadeUp 0.3s ease",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#22c55e",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          boxShadow: "0 0 0 6px #22c55e20",
        }}
      >
        {Ic.check(18)}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "#15803d",
            fontFamily: F.sans,
            marginBottom: 2,
          }}
        >
          Reactivation Verified — Reproducible ✓
        </div>
        <div style={{ fontSize: 13, color: "#166534", fontFamily: F.sans }}>
          All four stages passed. The sealed REE is byte-for-byte reproducible on this machine.
        </div>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
          alignItems: "flex-end",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, color: "#166534", fontFamily: F.mono, fontWeight: 600 }}>
          {new Date().toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span style={{ fontSize: 10, color: "#16a34a", fontFamily: F.sans }}>by reviewer</span>
      </div>
    </div>
  );
}

// ── Provenance chain ───────────────────────────────────────────────────────────
interface RvProvenanceChainProps {
  ree: Ree;
}
function RvProvenanceChain({ ree }: RvProvenanceChainProps) {
  const nodes = [
    {
      label: "Source Code",
      value: ree.origin_url,
      icon: Ic.link,
      color: "#0891b2",
      href: ree.origin_url,
    },
    {
      label: "Software Heritage",
      value: ree.swhid,
      icon: Ic.archive,
      color: "#e4572e",
      href: ree.swhid ? `https://archive.softwareheritage.org/${ree.swhid}` : null,
    },
    {
      label: "Zenodo DOI",
      value: ree.zenodo_doi,
      icon: Ic.globe,
      color: "#1d6fa4",
      href: ree.zenodo_doi ? `https://doi.org/${ree.zenodo_doi}` : null,
    },
    { label: "SBOM", value: ree.sbom, icon: Ic.package, color: "#16a34a" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {nodes.map((n, i) => {
        const set = !!n.value;
        return (
          <div key={i} style={{ display: "flex", gap: 10, alignItems: "stretch" }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 24,
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background: set ? `${n.color}18` : C.surfaceAlt,
                  border: `2px solid ${set ? n.color : C.borderMid}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: set ? n.color : C.textMuted,
                  flexShrink: 0,
                }}
              >
                {n.icon(9)}
              </div>
              {i < nodes.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    width: 2,
                    background: set ? `${n.color}40` : C.border,
                    minHeight: 10,
                  }}
                />
              )}
            </div>
            <div
              style={{
                flex: 1,
                paddingBottom: i < nodes.length - 1 ? 10 : 0,
                paddingTop: 1,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: set ? C.textMid : C.textMuted,
                  fontFamily: F.sans,
                  marginBottom: 1,
                }}
              >
                {n.label}
              </div>
              {set ? (
                n.href ? (
                  <a
                    href={n.href}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: n.color,
                      textDecoration: "none",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                      maxWidth: "100%",
                    }}
                  >
                    {n.value.length > 50 ? `${n.value.slice(0, 50)}…` : n.value}
                  </a>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: n.color,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                    }}
                  >
                    {n.value}
                  </span>
                )
              ) : (
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    color: C.textMuted,
                    fontStyle: "italic",
                  }}
                >
                  not set
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Pod Orbit Control — pod + arc progress ring + launch button ────────────────
interface PodOrbitControlProps {
  level: number;
  lv: Level;
  stepStates: Record<string, StepState>;
  allDone: boolean;
  isRunningAll: boolean;
  onRunAll: () => void;
}
function PodOrbitControl({
  level,
  lv,
  stepStates,
  allDone,
  isRunningAll,
  onRunAll,
}: PodOrbitControlProps) {
  const podSize = 300;
  const cx = podSize / 2,
    cy = podSize / 2;
  const ringR = cx - 6;
  const steps = REACTIVATION_STEPS;
  const gapDeg = 7;
  const segDeg = (360 - gapDeg * steps.length) / steps.length;

  const ringPt = (deg, r = ringR) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arcD = (startDeg, endDeg, r = ringR) => {
    const s = ringPt(startDeg, r),
      e = ringPt(endDeg, r);
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${endDeg - startDeg > 180 ? 1 : 0} 1 ${e.x} ${e.y}`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 24 }}>
      <div style={{ position: "relative", width: podSize, height: podSize }}>
        <div
          style={{
            position: "absolute",
            top: -14,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 3,
            whiteSpace: "nowrap",
          }}
        >
          <LevelBadge level={level} large />
        </div>
        <svg
          width={podSize}
          height={podSize}
          style={{ position: "absolute", inset: 0, overflow: "visible", zIndex: 2 }}
        >
          <title>Reactivation steps</title>
          <circle
            cx={cx}
            cy={cy}
            r={ringR}
            fill="none"
            stroke={lv.color}
            strokeWidth="1"
            opacity="0.12"
            strokeDasharray="4 6"
          />
          {steps.map((step, i) => {
            const startDeg = i * (segDeg + gapDeg),
              endDeg = startDeg + segDeg;
            const state = stepStates[step.key];
            const isDone = state === "done",
              isRun = state === "loading";
            const color = isDone ? "#22c55e" : isRun ? step.color : `${lv.color}30`;
            const width = isDone ? 9 : isRun ? 10 : 5;
            const midPt = ringPt(startDeg + segDeg / 2, ringR + 20);
            return (
              <g key={step.key}>
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={`${lv.color}15`}
                  strokeWidth="10"
                  fill="none"
                  strokeLinecap="round"
                />
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={color}
                  strokeWidth={width}
                  fill="none"
                  strokeLinecap="round"
                  style={{ transition: "stroke 0.4s, stroke-width 0.25s" }}
                />
                {isDone && (
                  <path
                    d={arcD(startDeg, endDeg)}
                    stroke="#22c55e"
                    strokeWidth="18"
                    fill="none"
                    strokeLinecap="round"
                    opacity="0.1"
                  />
                )}
                <circle
                  cx={midPt.x}
                  cy={midPt.y}
                  r={isDone ? 6 : isRun ? 5 : 4}
                  fill={isDone ? "#22c55e" : isRun ? step.color : `${lv.color}50`}
                  style={{ transition: "all 0.3s" }}
                />
                {isDone && <circle cx={midPt.x} cy={midPt.y} r={2.5} fill="white" />}
              </g>
            );
          })}
        </svg>
        <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
          <PodWidget level={level} size={podSize} />
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
          marginTop: 2,
        }}
      >
        <div
          style={{
            width: 2,
            height: 16,
            background: `linear-gradient(to bottom, ${lv.color}60, ${lv.color}20)`,
            borderRadius: 1,
          }}
        />
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: lv.color,
            opacity: 0.35,
            marginTop: -1,
          }}
        />
      </div>

      <button
        type="button"
        onClick={onRunAll}
        disabled={isRunningAll || allDone}
        onMouseEnter={(e) => {
          if (!isRunningAll && !allDone)
            e.currentTarget.style.transform = "translateY(-1px) scale(1.01)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "none";
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 40px",
          borderRadius: 14,
          background: allDone
            ? "linear-gradient(135deg, #f0fdf4, #dcfce7)"
            : isRunningAll
              ? `${lv.color}18`
              : `linear-gradient(135deg, ${lv.color} 0%, ${lv.ink} 100%)`,
          color: allDone ? "#16a34a" : isRunningAll ? lv.color : "#fff",
          border: allDone
            ? "1.5px solid #bbf7d0"
            : isRunningAll
              ? `1.5px solid ${lv.color}35`
              : "none",
          fontSize: 15,
          fontWeight: 700,
          fontFamily: F.sans,
          letterSpacing: 0.2,
          cursor: isRunningAll || allDone ? "default" : "pointer",
          boxShadow:
            !allDone && !isRunningAll
              ? `0 6px 28px ${lv.color}45, 0 2px 10px ${lv.color}30, inset 0 1px 0 rgba(255,255,255,0.22)`
              : allDone
                ? "0 3px 14px #22c55e20"
                : "none",
          transition: "all 0.2s",
        }}
      >
        <span
          style={{
            display: "flex",
            animation: isRunningAll ? "spin 0.9s linear infinite" : "none",
          }}
        >
          {allDone ? Ic.check(18) : isRunningAll ? Ic.loader(18) : Ic.play(18)}
        </span>
        {allDone ? "All stages verified" : isRunningAll ? "Reactivating…" : "Run Full Reactivation"}
      </button>

      <div
        style={{
          display: "flex",
          gap: 6,
          marginTop: 12,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {steps.map((step) => {
          const state = stepStates[step.key];
          const isDone = state === "done",
            isRun = state === "loading";
          return (
            <div
              key={step.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: 5,
                background: isDone ? "#f0fdf4" : isRun ? `${step.color}12` : C.surfaceAlt,
                border: `1px solid ${isDone ? "#bbf7d0" : isRun ? `${step.color}40` : C.border}`,
                transition: "all 0.3s",
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: isDone ? "#22c55e" : isRun ? step.color : C.borderMid,
                  boxShadow: isRun ? `0 0 6px ${step.color}` : "none",
                  transition: "all 0.3s",
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  fontWeight: isDone || isRun ? 600 : 400,
                  color: isDone ? "#16a34a" : isRun ? step.color : C.textMuted,
                }}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface ReviewerViewProps {
  ree?: Ree;
  onBack: () => void;
}
function ReviewerView({ ree: reeInput, onBack }: ReviewerViewProps) {
  const ree = reeInput || SEALED_DEMO_REE;
  const level = ree._evalLevel ?? 5;
  const lv = LEVELS[Math.min(level, 7)];
  const sealDate = ree._sealedAt
    ? new Date(ree._sealedAt).toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "unknown";

  const [stepStates, setStepStates] = useState<Record<string, StepState>>({});
  const [stepLogs, setStepLogs] = useState<Record<string, LogLine[]>>({});
  const initParams = () =>
    Object.fromEntries(
      REACTIVATION_STEPS.map((s) => [
        s.key,
        Object.fromEntries((s.params || []).map((p) => [p.key, p.default])),
      ]),
    );
  const [stepParams, setStepParams] = useState<Record<string, Record<string, unknown>>>(initParams);

  const setParam = (stepKey: string, paramKey: string, val: unknown) =>
    setStepParams((p) => ({ ...p, [stepKey]: { ...p[stepKey], [paramKey]: val } }));

  const runStep = async (key, params) => {
    const step = REACTIVATION_STEPS.find((s) => s.key === key);
    setStepStates((s) => ({ ...s, [key]: "loading" }));
    setStepLogs((l) => ({ ...l, [key]: step.logLines(ree, params) }));
    await new Promise((r) => setTimeout(r, 1200 + step.logLines(ree, params).length * 80));
    setStepStates((s) => ({ ...s, [key]: "done" }));
  };

  const allDone = REACTIVATION_STEPS.every((s) => stepStates[s.key] === "done");
  const isRunningAll = REACTIVATION_STEPS.some((s) => stepStates[s.key] === "loading");

  const runAll = async () => {
    for (const step of REACTIVATION_STEPS) {
      if (stepStates[step.key] === "done") continue;
      await runStep(step.key, stepParams[step.key]);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = C.textMid;
            e.currentTarget.style.background = C.surfaceAlt;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = C.textMuted;
            e.currentTarget.style.background = "none";
          }}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Explorer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: 6,
          }}
        >
          <span style={{ color: "#b45309", display: "flex" }}>{Ic.star(12)}</span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "#92400e",
              fontFamily: F.sans,
              letterSpacing: 0.3,
            }}
          >
            REVIEWER MODE
          </span>
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        {/* Sidebar */}
        <aside
          style={{
            width: 256,
            borderRight: `1px solid ${C.border}`,
            background: C.surface,
            overflowY: "auto",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "14px 16px 12px",
              background: `linear-gradient(160deg, ${lv.bg} 0%, ${C.surface} 100%)`,
              borderBottom: `1px solid ${lv.color}25`,
            }}
          >
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: 1.4,
                color: lv.color,
                textTransform: "uppercase",
                fontFamily: F.sans,
                marginBottom: 5,
              }}
            >
              Specimen Pod
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                fontFamily: F.mono,
                marginBottom: 8,
                wordBreak: "break-all",
              }}
            >
              {ree.name}
            </div>
            <LevelBadge level={level} />
            <div
              style={{
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 9px",
                background: "rgba(255,255,255,0.7)",
                border: `1px solid ${lv.color}25`,
                borderRadius: 6,
              }}
            >
              <span style={{ color: lv.color, display: "flex", flexShrink: 0 }}>{Ic.lock(10)}</span>
              <div>
                <div style={{ fontSize: 9, fontWeight: 600, color: lv.color, fontFamily: F.sans }}>
                  Sealed
                </div>
                <div style={{ fontSize: 10, fontFamily: F.mono, color: C.textMid }}>{sealDate}</div>
              </div>
            </div>
          </div>
          <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}` }}>
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: 1.2,
                color: C.textMuted,
                textTransform: "uppercase",
                fontFamily: F.sans,
                marginBottom: 10,
              }}
            >
              Metadata
            </div>
            <MetaRow label="Origin URL" value={ree.origin_url} mono href={ree.origin_url} />
            <MetaRow label="Runtime" value={ree.runtime} mono color={C.textMid} />
            <MetaRow label="Build Script" value={ree.build_runtime_script} mono color={C.textMid} />
            <MetaRow
              label="Activation Script"
              value={ree.activation_script}
              mono
              color={C.textMid}
            />
            <MetaRow label="SBOM" value={ree.sbom} mono color={C.textMid} />
            {ree.hardware_description && (
              <div style={{ paddingTop: 8 }}>
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: 1.2,
                    color: C.textMuted,
                    textTransform: "uppercase",
                    fontFamily: F.sans,
                    marginBottom: 6,
                  }}
                >
                  Hardware
                </div>
                {Object.entries(ree.hardware_description)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div
                      key={k}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 11,
                        marginBottom: 3,
                      }}
                    >
                      <span style={{ color: C.textMuted, fontFamily: F.sans }}>{k}</span>
                      <span style={{ fontFamily: F.mono, color: C.textMid }}>{v}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
          <div style={{ padding: "14px 16px" }}>
            <div
              style={{
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: 1.2,
                color: C.textMuted,
                textTransform: "uppercase",
                fontFamily: F.sans,
                marginBottom: 12,
              }}
            >
              Provenance
            </div>
            <RvProvenanceChain ree={ree} />
          </div>
        </aside>

        {/* Main */}
        <main
          style={{
            flex: 1,
            overflowY: "auto",
            minWidth: 0,
            background: `linear-gradient(180deg, ${lv.bg}50 0%, ${C.bg} 320px)`,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              borderBottom: `1px solid ${C.border}`,
              paddingBottom: 28,
            }}
          >
            <PodOrbitControl
              level={level}
              lv={lv}
              stepStates={stepStates}
              allDone={allDone}
              isRunningAll={isRunningAll}
              onRunAll={runAll}
            />
          </div>
          <div style={{ padding: "20px 28px" }}>
            {allDone && (
              <div style={{ marginBottom: 20 }}>
                <RvVerdictBanner allDone={allDone} />
              </div>
            )}
            <div style={{ maxWidth: 660 }}>
              {REACTIVATION_STEPS.map((step, i) => {
                const prevDone = i === 0 || stepStates[REACTIVATION_STEPS[i - 1].key] === "done";
                return (
                  <RvStepCard
                    key={step.key}
                    step={step}
                    index={i}
                    state={stepStates[step.key] || "idle"}
                    log={stepLogs[step.key] || null}
                    params={stepParams[step.key]}
                    onSetParam={setParam}
                    onRun={runStep}
                    isLast={i === REACTIVATION_STEPS.length - 1}
                    prevDone={prevDone}
                  />
                );
              })}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<AppPage>(APP_PAGE.LANDING);
  return (
    <>
      <style>{GLOBAL_CSS}</style>
      {page === APP_PAGE.LANDING && <Landing onLoad={(p) => setPage(p)} />}
      {page === APP_PAGE.EXPLORER && <Explorer onBack={() => setPage(APP_PAGE.LANDING)} />}
      {page === APP_PAGE.REVIEWER && <ReviewerView onBack={() => setPage(APP_PAGE.LANDING)} />}
    </>
  );
}
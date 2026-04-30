import type React from "react";
import { useMemo, useState } from "react";
import type { ReeFile } from "../../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { MOCK_FILES } from "../../../../infra/workspace/InMemoryWorkspaceGateway";
import { FileNode } from "../../../shared/components/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { fmtBytes } from "../../../shared/formatting";
import {
  C,
  F,
  hoverBorderColor,
  hoverColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
  S_SECTION_LABEL,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import { WorkflowPageHeader } from "../../components/pageChrome";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

const FILE_VIEWER_MAX_CHARS = 120_000;
const FILE_VIEWER_MAX_LINES = 2_000;

const TEXT_FILE_EXTENSIONS = new Set([
  "txt",
  "md",
  "json",
  "yaml",
  "yml",
  "xml",
  "toml",
  "ini",
  "cfg",
  "conf",
  "sh",
  "py",
  "js",
  "ts",
  "tsx",
  "jsx",
  "css",
  "html",
  "csv",
  "log",
  "dockerfile",
]);

function isLikelyTextFile(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  if (lower === "dockerfile" || lower.endsWith(".dockerfile")) {
    return true;
  }
  const ext = lower.includes(".") ? lower.split(".").pop() || "" : "";
  return TEXT_FILE_EXTENSIONS.has(ext);
}

function flattenTree(nodes: FileTreeNode[]): FileTreeNode[] {
  const result: FileTreeNode[] = [];
  for (const node of nodes || []) {
    if (node.type === "folder") result.push(...flattenTree(node.children || []));
    else result.push(node);
  }
  return result;
}

interface FlatTreeEntry {
  node: FileTreeNode;
  path: string;
}

function flattenTreeWithPaths(nodes: FileTreeNode[], prefix = ""): FlatTreeEntry[] {
  const result: FlatTreeEntry[] = [];
  for (const node of nodes || []) {
    const currentPath = prefix ? `${prefix}/${node.name}` : node.name;
    if (node.type === "folder") {
      result.push(...flattenTreeWithPaths(node.children || [], currentPath));
    } else {
      result.push({ node, path: currentPath });
    }
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
    const existing = nodes.find((node) => node.type === "folder" && node.name === folderName);
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
    const existingFileIdx = cursor.findIndex(
      (node) => node.type === "file" && node.name === fileName,
    );
    const fileNode: FileTreeNode = {
      id: file.id,
      name: fileName,
      type: "file",
      content: file.content,
      size: file.size,
      tag: file.tag,
    };
    if (existingFileIdx >= 0) cursor[existingFileIdx] = fileNode;
    else cursor.push(fileNode);
  }

  return roots;
}

interface FileViewerProps {
  file: FileTreeNode | ReeFile;
  onClose: () => void;
  label?: string;
  onDownload?: () => Promise<void>;
}

function FileViewer({ file, onClose, label, onDownload }: FileViewerProps) {
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const likelyTextFile = isLikelyTextFile(file.name);
  const unavailableInlineText =
    !file.content && typeof file.size === "number" && file.size > 0 && likelyTextFile;
  const hasBinaryContent =
    !file.content && typeof file.size === "number" && file.size > 0 && !likelyTextFile;
  const binaryLabel = hasBinaryContent ? `Binary file (${fmtBytes(file.size || 0)})` : null;
  const textUnavailableLabel = unavailableInlineText
    ? `Text file (${fmtBytes(file.size || 0)}) was not inlined to keep memory usage low.`
    : null;
  const shouldOfferDownload = (unavailableInlineText || hasBinaryContent) && !!onDownload;
  const fullText = file.content || "";
  const truncatedByChars = !hasBinaryContent && fullText.length > FILE_VIEWER_MAX_CHARS;
  const previewText = truncatedByChars ? fullText.slice(0, FILE_VIEWER_MAX_CHARS) : fullText;
  const previewLines = previewText.split("\n");
  const truncatedByLines = !hasBinaryContent && previewLines.length > FILE_VIEWER_MAX_LINES;
  const truncated = truncatedByChars || truncatedByLines;
  const copy = () => {
    navigator.clipboard?.writeText(file.content || binaryLabel || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const download = async () => {
    if (!onDownload || downloading) return;
    setDownloading(true);
    try {
      await onDownload();
    } finally {
      setDownloading(false);
    }
  };
  const lines = hasBinaryContent
    ? [binaryLabel || "Binary file", "Content preview is unavailable for this file type."]
    : unavailableInlineText
      ? [
          textUnavailableLabel || "Text preview unavailable",
          "Open/download raw content if you need full file contents.",
        ]
      : truncatedByLines
        ? previewLines.slice(0, FILE_VIEWER_MAX_LINES)
        : previewLines;

  return (
    <div
      style={{ display: "flex", flexDirection: "column", height: "100%", background: "#f8fafc" }}
    >
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
        {shouldOfferDownload ? (
          <button
            type="button"
            onClick={download}
            style={{
              ...actionBtn({
                background: "none",
                border: `1px solid ${C.border}`,
                borderRadius: 4,
                padding: "2px 8px",
                fontSize: 10,
                color: C.textMuted,
                transition: "all 0.12s",
              }),
              flexShrink: 0,
            }}
            {...hoverIf(!downloading, hoverBorderColor(C.accent, C.border))}
            {...hoverIf(!downloading, hoverColor(C.accent, C.textMuted))}
            disabled={downloading}
          >
            {downloading ? "downloading…" : "download"}
          </button>
        ) : (
          <button
            type="button"
            onClick={copy}
            style={{
              ...actionBtn({
                background: "none",
                border: `1px solid ${C.border}`,
                borderRadius: 4,
                padding: "2px 8px",
                fontSize: 10,
                color: copied ? "#16a34a" : C.textMuted,
                transition: "all 0.12s",
              }),
              flexShrink: 0,
            }}
            {...hoverIf(!copied, hoverBorderColor(C.accent, C.border))}
            {...hoverIf(!copied, hoverColor(C.accent, C.textMuted))}
          >
            {copied ? "✓ copied" : "copy"}
          </button>
        )}
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
          {...hoverColor(C.text, C.textMuted)}
        >
          {Ic.x(12)}
        </button>
      </div>
      <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
        {truncated && (
          <div
            style={{
              margin: "0 10px 8px",
              padding: "8px 10px",
              borderRadius: 6,
              border: `1px solid ${C.border}`,
              background: C.surfaceAlt,
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.sans,
            }}
          >
            Preview truncated to keep the UI responsive.
          </div>
        )}
        {(() => {
          const lineCounts = new Map<string, number>();
          return lines.map((line, i) => {
            const occurrenceIndex = lineCounts.get(line) ?? 0;
            lineCounts.set(line, occurrenceIndex + 1);
            return (
              <div
                key={`dockerfile-line-${line}-${occurrenceIndex}`}
                style={{ display: "flex", alignItems: "baseline" }}
              >
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
                    color: hasBinaryContent
                      ? C.textMuted
                      : unavailableInlineText
                        ? C.textMuted
                        : line.startsWith("#")
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
            );
          });
        })()}
      </div>
    </div>
  );
}

interface PageFilesProps {
  files: FileTreeNode[];
  reeFiles: ReeFile[];
  onDownloadWorkspaceFile?: (path: string, suggestedName?: string) => Promise<void>;
}

export function PageFiles({ files, reeFiles, onDownloadWorkspaceFile }: PageFilesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sourceFiles = files || MOCK_FILES;
  const reeFileTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const sourceFlatEntries = useMemo(() => flattenTreeWithPaths(sourceFiles), [sourceFiles]);
  const reeFlatEntries = useMemo(() => flattenTreeWithPaths(reeFileTree), [reeFileTree]);
  const reeFlatFiles = useMemo(() => flattenTree(reeFileTree), [reeFileTree]);

  const selectedSourceEntry = selectedId
    ? sourceFlatEntries.find((entry) => entry.node.id === selectedId) || null
    : null;
  const selectedReeEntry = selectedId
    ? reeFlatEntries.find((entry) => entry.node.id === selectedId) || null
    : null;
  const selectedFile = selectedSourceEntry?.node || selectedReeEntry?.node || null;

  const SectionHeader = ({
    label,
    badge,
    color,
  }: {
    label: string;
    badge?: string;
    color: string;
  }) => (
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
          ...S_SECTION_LABEL,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 1.3,
          color: C.textMid,
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
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color="#6366f1"
        icon={Ic.files(18)}
        title="Files"
        subtitle="Inspect workspace inputs and generated REE files side by side"
        tips={[
          "Use this view to verify paths referenced by source, runtime, scripts, and SBOM fields.",
          "Workspace is read-only here; run lifecycle steps to generate or update REE files.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
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
            <SectionHeader label="Workspace" badge="read-only" color="#f59e0b" />
            <div style={{ padding: "4px 4px 8px" }}>
              {sourceFiles.map((sourceNode) => (
                <FileNode
                  key={sourceNode.id}
                  node={sourceNode}
                  onSelect={(selectedNode) => setSelectedId(selectedNode.id)}
                  selectedId={selectedId}
                />
              ))}
            </div>

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
                reeFileTree.map((reeNode) => (
                  <FileNode
                    key={reeNode.id}
                    node={reeNode}
                    onSelect={(selectedNode) => setSelectedId(selectedNode.id)}
                    selectedId={selectedId}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {selectedFile ? (
          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            <FileViewer
              file={selectedFile}
              onClose={() => setSelectedId(null)}
              label={reeFlatFiles.find((f) => f.id === selectedId) ? "ree" : "workspace"}
              onDownload={
                selectedSourceEntry?.path && onDownloadWorkspaceFile
                  ? () => onDownloadWorkspaceFile(selectedSourceEntry.path, selectedFile.name)
                  : undefined
              }
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
    </div>
  );
}

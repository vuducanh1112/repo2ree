import type React from "react";
import { useState } from "react";
import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { splitDisplayPath } from "../../../../../core/workspace/PathUtils";
import { Ic } from "../../../shared/components/Icon";
import { fmtBytes } from "../../../shared/formatting";
import { lgColors, lgSyntax, lgTree } from "../../../theme/lightGlassTheme";
import {
  F,
  hoverBorderColor,
  hoverColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
} from "../../../theme/theme";
import { FILE_VIEWER_MAX_CHARS, FILE_VIEWER_MAX_LINES, isLikelyTextFile } from "./filesPageHelpers";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  background: "none",
  border: `1px solid ${lgTree.pane.borderColor}`,
  borderRadius: 4,
  padding: "2px 8px",
  fontSize: 10,
  color: lgColors.textMuted,
  transition: "all 0.12s",
  flexShrink: 0,
  ...extra,
});

interface FileViewerProps {
  file: FileTreeNode | ReeFile;
  path?: string | null;
  onClose: () => void;
  label?: string;
  onDownload?: () => Promise<void>;
}

export function FileViewer({ file, path, onClose, label, onDownload }: FileViewerProps) {
  const [copied, setCopied] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);
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
  const displayPath = path || file.name;
  const { dirPrefix, baseName } = splitDisplayPath(displayPath);
  const copy = () => {
    navigator.clipboard?.writeText(file.content || binaryLabel || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const copyPath = () => {
    if (!path) return;
    navigator.clipboard?.writeText(path);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 1800);
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
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: lgTree.viewerBg,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: `1px solid ${lgTree.pane.borderColor}`,
          background: lgTree.viewerHeaderBg,
          backdropFilter: "blur(8px)",
          flexShrink: 0,
        }}
      >
        <span style={{ display: "flex", color: lgColors.textMuted, flexShrink: 0 }}>
          {Ic.file(12)}
        </span>
        <span
          title={displayPath}
          style={{ display: "flex", flex: 1, minWidth: 0, fontFamily: F.mono, fontSize: 12 }}
        >
          {dirPrefix && (
            <span
              style={{
                color: lgColors.textMuted,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                minWidth: 0,
                direction: "rtl",
                textAlign: "left",
              }}
            >
              {dirPrefix}
            </span>
          )}
          <span
            style={{ color: lgColors.text, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0 }}
          >
            {baseName}
          </span>
        </span>
        {label && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: 0.5,
              color: lgColors.textMuted,
              background: lgTree.chipBg,
              border: `1px solid ${lgTree.pane.borderColor}`,
              borderRadius: 3,
              padding: "1px 5px",
              fontFamily: F.sans,
              flexShrink: 0,
            }}
          >
            {label}
          </span>
        )}
        {path && (
          <button
            type="button"
            onClick={copyPath}
            title="Copy path"
            style={actionBtn(
              copiedPath ? { color: lgColors.success, borderColor: "rgba(34, 197, 94, 0.42)" } : {},
            )}
            {...hoverIf(!copiedPath, hoverBorderColor(lgColors.blue, lgTree.pane.borderColor))}
            {...hoverIf(!copiedPath, hoverColor(lgColors.blue, lgColors.textMuted))}
          >
            {copiedPath ? "✓ path" : "path"}
          </button>
        )}
        {shouldOfferDownload ? (
          <button
            type="button"
            onClick={download}
            style={actionBtn()}
            {...hoverIf(!downloading, hoverBorderColor(lgColors.blue, lgTree.pane.borderColor))}
            {...hoverIf(!downloading, hoverColor(lgColors.blue, lgColors.textMuted))}
            disabled={downloading}
          >
            {downloading ? "downloading…" : "download"}
          </button>
        ) : (
          <button
            type="button"
            onClick={copy}
            style={actionBtn(copied ? { color: lgColors.success } : {})}
            {...hoverIf(!copied, hoverBorderColor(lgColors.blue, lgTree.pane.borderColor))}
            {...hoverIf(!copied, hoverColor(lgColors.blue, lgColors.textMuted))}
          >
            {copied ? "✓ copied" : "copy"}
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          title="Close"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: lgColors.textMuted,
            display: "flex",
            padding: 2,
            borderRadius: 4,
          }}
          {...hoverColor(lgColors.text, lgColors.textMuted)}
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
              border: `1px solid ${lgTree.pane.borderColor}`,
              background: lgTree.calloutBg,
              fontSize: 11,
              color: lgColors.textMuted,
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
                key={`viewer-line-${line}-${occurrenceIndex}`}
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
                    color: lgSyntax.lineNumber,
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
                    color:
                      hasBinaryContent || unavailableInlineText
                        ? lgColors.textMuted
                        : line.startsWith("#")
                          ? lgSyntax.comment
                          : /^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)
                            ? lgSyntax.keyword
                            : /^(set |echo |docker |pip )/.test(line)
                              ? lgSyntax.command
                              : /^\s*"/.test(line) && line.includes(":")
                                ? lgSyntax.string
                                : lgColors.text,
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

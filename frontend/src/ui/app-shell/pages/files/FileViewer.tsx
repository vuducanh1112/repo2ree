import type React from "react";
import { useState } from "react";
import type { ReeFile } from "../../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { fmtBytes } from "../../../shared/formatting";
import {
  C,
  F,
  hoverBorderColor,
  hoverColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
} from "../../../theme/theme";
import { FILE_VIEWER_MAX_CHARS, FILE_VIEWER_MAX_LINES, isLikelyTextFile } from "./filesPageHelpers";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

interface FileViewerProps {
  file: FileTreeNode | ReeFile;
  onClose: () => void;
  label?: string;
  onDownload?: () => Promise<void>;
}

export function FileViewer({ file, onClose, label, onDownload }: FileViewerProps) {
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

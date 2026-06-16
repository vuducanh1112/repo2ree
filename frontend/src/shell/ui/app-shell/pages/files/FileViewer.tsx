import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { fmtBytes } from "../../../shared/formatting";
import { lgColors, lgSyntax, lgTree } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { FILE_VIEWER_MAX_CHARS, FILE_VIEWER_MAX_LINES, isLikelyTextFile } from "./filesPageHelpers";

function isShellLike(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return (
    lower === "dockerfile" ||
    lower.endsWith(".dockerfile") ||
    lower.endsWith(".sh") ||
    lower.endsWith(".bash")
  );
}

function classifyLine(line: string): string {
  if (line.startsWith("#")) return lgSyntax.comment;
  if (/^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)) return lgSyntax.keyword;
  if (/^(set |echo |docker |pip )/.test(line)) return lgSyntax.command;
  if (/^\s*"/.test(line) && line.includes(":")) return lgSyntax.string;
  return lgColors.text;
}

function renderLines(lines: string[], muted: boolean, syntaxColor: boolean) {
  return lines.map((line, i) => (
    // biome-ignore lint/suspicious/noArrayIndexKey: static file content, lines never reorder
    <div key={i} style={{ display: "flex", alignItems: "baseline" }}>
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
          color: muted ? lgColors.textMuted : syntaxColor ? classifyLine(line) : lgColors.text,
        }}
      >
        {line || " "}
      </span>
    </div>
  ));
}

interface FileViewerProps {
  file: FileTreeNode | ReeFile;
}

export function FileViewer({ file }: FileViewerProps) {
  const likelyTextFile = isLikelyTextFile(file.name);
  const unavailableInlineText =
    !file.content && typeof file.size === "number" && file.size > 0 && likelyTextFile;
  const hasBinaryContent =
    !file.content && typeof file.size === "number" && file.size > 0 && !likelyTextFile;
  const binaryLabel = hasBinaryContent ? `Binary file (${fmtBytes(file.size || 0)})` : null;
  const textUnavailableLabel = unavailableInlineText
    ? `Text file (${fmtBytes(file.size || 0)}) was not inlined to keep memory usage low.`
    : null;
  const fullText = file.content || "";
  const truncatedByChars = !hasBinaryContent && fullText.length > FILE_VIEWER_MAX_CHARS;
  const previewText = truncatedByChars ? fullText.slice(0, FILE_VIEWER_MAX_CHARS) : fullText;
  const previewLines = previewText.split("\n");
  const truncatedByLines = !hasBinaryContent && previewLines.length > FILE_VIEWER_MAX_LINES;
  const truncated = truncatedByChars || truncatedByLines;
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
        flex: 1,
        minWidth: 0,
        background: lgTree.viewerBg,
      }}
    >
      <div style={{ overflow: "auto", flex: 1, padding: "8px 0" }}>
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
        {renderLines(lines, hasBinaryContent || unavailableInlineText, isShellLike(file.name))}
      </div>
    </div>
  );
}

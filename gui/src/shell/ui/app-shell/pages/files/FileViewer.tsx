import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import {
  FILE_VIEWER_MAX_CHARS,
  FILE_VIEWER_MAX_LINES,
  isLikelyTextFile,
} from "@core/workspace/reeFileTree";
import { fmtBytes } from "@shell/ui/shared/formatting";
import styles from "./FileViewer.module.css";

function isShellLike(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return (
    lower === "dockerfile" ||
    lower.endsWith(".dockerfile") ||
    lower.endsWith(".sh") ||
    lower.endsWith(".bash")
  );
}

/** Which of the four kinds a line is, or undefined for ordinary content. The
 * classifier names the kind; FileViewer.module.css decides how it reads. */
function classifyLine(line: string): string | undefined {
  if (line.startsWith("#")) return "comment";
  if (/^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)) return "keyword";
  if (/^(set |echo |docker |pip )/.test(line)) return "command";
  if (/^\s*"/.test(line) && line.includes(":")) return "string";
  return undefined;
}

function renderLines(lines: string[], muted: boolean, syntaxColor: boolean) {
  return lines.map((line, i) => (
    // biome-ignore lint/suspicious/noArrayIndexKey: static file content, lines never reorder
    <div key={i} className={styles.line}>
      <span className={styles.lineNumber}>{i + 1}</span>
      <span
        className={styles.code}
        data-muted={muted || undefined}
        data-syntax={syntaxColor ? classifyLine(line) : undefined}
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
    <div className={styles.viewer}>
      <div className={styles.scroll}>
        {truncated && (
          <div className={styles.callout}>Preview truncated to keep the UI responsive.</div>
        )}
        {renderLines(lines, hasBinaryContent || unavailableInlineText, isShellLike(file.name))}
      </div>
    </div>
  );
}

import { C, F } from "../../../theme/theme";

interface FileTypeStyle {
  color: string;
  bg: string;
  border: string;
  label: string;
}

export const FILE_TYPE_COLORS: Record<string, FileTypeStyle> = {
  shell: { color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0", label: "sh" },
  dockerfile: { color: "#0891b2", bg: "#ecfeff", border: "#a5f3fc", label: "container" },
  json: { color: "#7c3aed", bg: "#f5f3ff", border: "#ddd6fe", label: "json" },
  python: { color: "#2563eb", bg: "#eff6ff", border: "#bfdbfe", label: "py" },
  nix: { color: "#e4572e", bg: "#fff7f5", border: "#fbd0c4", label: "nix" },
  markdown: { color: "#64748b", bg: "#f8fafc", border: "#e2e8f0", label: "md" },
  config: { color: "#b45309", bg: "#fffbeb", border: "#fde68a", label: "cfg" },
  text: { color: "#475569", bg: "#f8fafc", border: "#e2e8f0", label: "txt" },
};

export const PREVIEW_LINES = 6;

function codeColor(line: string): string {
  if (line.startsWith("#")) return "#94a3b8";
  if (/^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)) return "#0369a1";
  if (/^(set |echo |docker |pip |apt-get )/.test(line)) return "#15803d";
  if (line.includes("=") && !line.startsWith(" ") && !line.includes("==")) return "#b45309";
  return C.text;
}

interface CodeLineListProps {
  lines: string[];
  paddingRight?: number;
  startLine?: number;
}

export function CodeLineList({ lines, paddingRight = 16, startLine = 1 }: CodeLineListProps) {
  let lineNumber = startLine - 1;
  const seenLines = new Map<string, number>();

  return (
    <>
      {lines.map((line) => {
        lineNumber += 1;
        const occurrence = (seenLines.get(line) ?? 0) + 1;
        seenLines.set(line, occurrence);
        return (
          <div
            key={`${line}::${occurrence}`}
            style={{
              display: "flex",
              alignItems: "baseline",
            }}
          >
            <span
              style={{
                display: "inline-block",
                minWidth: 40,
                textAlign: "right",
                paddingRight,
                paddingLeft: 12,
                fontSize: 11,
                fontFamily: F.mono,
                color: C.borderMid,
                userSelect: "none",
                flexShrink: 0,
              }}
            >
              {lineNumber}
            </span>
            <span
              style={{
                fontSize: 12,
                fontFamily: F.mono,
                lineHeight: 1.75,
                whiteSpace: "pre",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "block",
                paddingRight,
                color: codeColor(line),
              }}
            >
              {line || " "}
            </span>
          </div>
        );
      })}
    </>
  );
}

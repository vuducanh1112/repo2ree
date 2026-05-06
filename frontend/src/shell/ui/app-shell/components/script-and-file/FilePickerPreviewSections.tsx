import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverColor } from "../../../theme/theme";
import { CodeLineList, PREVIEW_LINES } from "./shared";
export function FilePickerWarning(props: {
  notFound: boolean;
  wrongFormat: boolean;
  placeholder?: string;
}) {
  if (!(props.notFound || props.wrongFormat)) return null;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "5px 10px",
        background: "#fff7ed",
        border: "1px solid #fed7aa",
        borderTop: "none",
        borderRadius: "0 0 6px 6px",
        animation: "fadeUp 0.15s ease",
      }}
    >
      <span style={{ fontSize: 11, color: "#c2410c", fontFamily: F.sans }}>
        {props.wrongFormat && props.notFound
          ? `Wrong format — expected ${props.placeholder || "the required format"}. File not found either.`
          : props.wrongFormat
            ? `Wrong format — this field only accepts ${props.placeholder || "the required format"}. Field not saved.`
            : "File not found in repository — field not saved until the path resolves."}
      </span>
    </div>
  );
}

export function FilePickerPreview(props: {
  isValid: boolean | null;
  previewOpen: boolean;
  matchedFile: { content?: string } | null;
  trimmedDraft: string;
  typeStyle: { label: string; bg: string; color: string; border: string };
  previewLines: string[];
  fileLineCount: number;
  onClose: () => void;
}) {
  if (!(props.isValid && props.previewOpen && props.matchedFile)) return null;
  const hasMore = props.fileLineCount > PREVIEW_LINES;
  return (
    <div
      style={{
        border: "1.5px solid #22c55e",
        borderTop: "none",
        borderRadius: "0 0 7px 7px",
        background: C.surfaceAlt,
        overflow: "hidden",
        animation: "fadeUp 0.15s ease",
      }}
    >
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
          <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMid, letterSpacing: 0.3 }}>
            {props.trimmedDraft}
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
              background: props.typeStyle.bg,
              color: props.typeStyle.color,
              border: `1px solid ${props.typeStyle.border}`,
            }}
          >
            {props.typeStyle.label}
          </span>
        </div>
        <button
          type="button"
          onClick={props.onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: C.textMuted,
            display: "flex",
            padding: "2px",
            borderRadius: 3,
          }}
          {...hoverColor(C.textMid, C.textMuted)}
        >
          {Ic.x(12)}
        </button>
      </div>

      <div style={{ padding: "8px 0 6px" }}>
        <CodeLineList lines={props.previewLines} paddingRight={14} />
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
            … {props.fileLineCount - PREVIEW_LINES} more lines
          </div>
        )}
      </div>
    </div>
  );
}

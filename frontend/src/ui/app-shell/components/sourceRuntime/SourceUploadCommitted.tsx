import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBorderColor, hoverColor } from "../../../theme/theme";

interface SourceUploadCommittedProps {
  committedName: string;
  inputDisabled: boolean;
  onReplace: () => void;
}

export function SourceUploadCommitted({
  committedName,
  inputDisabled,
  onReplace,
}: SourceUploadCommittedProps) {
  return (
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
      <span
        style={{
          color: "#16a34a",
          display: "flex",
        }}
      >
        {Ic.archive()}
      </span>
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
      {!inputDisabled && (
        <button
          type="button"
          onClick={onReplace}
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
          {...hoverBorderColor(C.accent, C.border)}
          {...hoverColor(C.accent, C.textMuted)}
        >
          {Ic.upload(11)} Replace
        </button>
      )}
    </div>
  );
}

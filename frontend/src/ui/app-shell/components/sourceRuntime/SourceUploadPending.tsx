import type { SourceUploadCommit } from "../../../../domain/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBrightness, hoverColor } from "../../../theme/theme";

interface SourceUploadPendingProps {
  pending: SourceUploadCommit;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SourceUploadPending({ pending, onConfirm, onCancel }: SourceUploadPendingProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 5,
        marginBottom: 8,
      }}
    >
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
        <span
          style={{
            color: "#d97706",
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
          onClick={onConfirm}
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
          {...hoverBrightness(96)}
        >
          {Ic.check(11)} Add to workspace
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: C.textMuted,
            display: "flex",
            padding: 2,
            borderRadius: 4,
          }}
          {...hoverColor("#dc2626", C.textMuted)}
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
        {Ic.info(10)} Setting a new source will reset all downstream results.
      </div>
    </div>
  );
}

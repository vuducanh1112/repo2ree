import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { C, F } from "../../../theme/theme";

interface SourceUploadDropzoneProps {
  dragging: boolean;
  inputDisabled: boolean;
  onDragOver: (event: React.DragEvent<HTMLButtonElement>) => void;
  onDragLeave: () => void;
  onDrop: (event: React.DragEvent<HTMLButtonElement>) => void;
  onClick: () => void;
}

export function SourceUploadDropzone({
  dragging,
  inputDisabled,
  onDragOver,
  onDragLeave,
  onDrop,
  onClick,
}: SourceUploadDropzoneProps) {
  return (
    <button
      type="button"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onClick}
      disabled={inputDisabled}
      style={{
        ...{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          padding: "22px 16px",
          borderRadius: 8,
          transition: "all 0.15s",
          width: "100%",
          appearance: "none",
        },
        cursor: inputDisabled ? "default" : "pointer",
        border: `1.5px dashed ${dragging ? C.accent : C.borderMid}`,
        background: dragging ? C.accentBg : C.bg,
        opacity: inputDisabled ? 0.55 : 1,
      }}
      onMouseEnter={(mouseEvent) => {
        if (!inputDisabled) {
          mouseEvent.currentTarget.style.borderColor = C.accent;
          mouseEvent.currentTarget.style.background = C.accentBg;
        }
      }}
      onMouseLeave={(mouseEvent) => {
        if (!dragging) {
          mouseEvent.currentTarget.style.borderColor = C.borderMid;
          mouseEvent.currentTarget.style.background = C.bg;
        }
      }}
    >
      <span
        style={{
          ...{
            display: "flex",
          },
          color: dragging ? C.accent : C.textMuted,
        }}
      >
        {Ic.upload(18)}
      </span>
      <span
        style={{
          ...{
            fontSize: 13,
            fontFamily: F.sans,
          },
          color: dragging ? C.accent : C.textMid,
        }}
      >
        Drop archive or{" "}
        <span
          style={{
            color: C.accent,
            fontWeight: 600,
          }}
        >
          browse archive
        </span>
      </span>
      <span
        style={{
          fontSize: 11,
          color: C.textMuted,
          fontFamily: F.mono,
          marginTop: 4,
        }}
      >
        .zip · .tar · .tar.gz
      </span>
    </button>
  );
}

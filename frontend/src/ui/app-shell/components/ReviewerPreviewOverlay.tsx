import type React from "react";
import type { Level, StepState } from "../../../core/ree-assembly/assemblyStepTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import { ReviewerView } from "../../reviewer/ReviewerView";
import { Ic } from "../../shared/components/Icon";
import {
  F,
  hoverBg,
  hoverColor,
  S_ACTION_BUTTON_BASE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_SECTION_LABEL,
} from "../../theme/theme";

interface ReviewerPreviewOverlayProps {
  open: boolean;
  ree: ReeEditorViewModel;
  onClose: () => void;
  PodOrbitControl: React.ComponentType<{
    level: number;
    levelMeta: Level;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function ReviewerPreviewOverlay({
  open,
  ree,
  onClose,
  PodOrbitControl,
}: ReviewerPreviewOverlayProps) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9000,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          height: 40,
          background: "#0f172a",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          flexShrink: 0,
        }}
      >
        <div style={S_FLEX_ROW_CENTER_GAP_6}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#f59e0b",
              boxShadow: "0 0 6px #f59e0b80",
            }}
          />
          <span
            style={{
              ...S_SECTION_LABEL,
              color: "#94a3b8",
            }}
          >
            Reviewer Preview
          </span>
        </div>
        <span style={{ fontSize: 11, color: "#475569", fontFamily: F.sans }}>
          — this is how a reviewer will see your sealed REE
        </span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={onClose}
          style={{
            ...actionBtn({
              padding: "5px 12px",
              borderRadius: 6,
              border: "1px solid #334155",
              background: "#1e293b",
              color: "#94a3b8",
              fontSize: 12,
            }),
            display: "flex",
            alignItems: "center",
            gap: 6,
            cursor: "pointer",
          }}
          {...hoverBg("#334155", "#1e293b")}
          {...hoverColor("#e2e8f0", "#94a3b8")}
        >
          {Ic.x(12)} Exit Preview
        </button>
      </div>
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <ReviewerView ree={ree} onBack={onClose} PodOrbitControl={PodOrbitControl} />
      </div>
    </div>
  );
}

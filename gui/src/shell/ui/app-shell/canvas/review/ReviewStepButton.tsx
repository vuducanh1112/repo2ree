import type { ReviewStepKey, ReviewStepStatus } from "@core/reviews/reviewDag";
import type { ReactNode } from "react";
import { Ic } from "../../../shared/components/Icon";
import { translucent } from "../../../theme/appearance";
import { C, F } from "../../../theme/theme";

const STATUS_META: Record<ReviewStepStatus, { label: string; color: string }> = {
  unavailable: { label: "Coming next", color: C.textMuted },
  ready: { label: "Ready", color: C.textMuted },
  queued: { label: "Queued", color: "#d97706" },
  running: { label: "Running", color: C.accent },
  succeeded: { label: "Complete", color: C.done },
  identical: { label: "Identical", color: C.done },
  equivalent: { label: "Equivalent", color: "#0891b2" },
  // The ordinary pass for a result: the author's own verify script accepted it.
  // Distinct from "identical" because matching output bytes are a stronger and
  // rarer thing, and from "complete" because this is a verdict, not a lifecycle
  // state.
  reproduced: { label: "Reproduced", color: C.done },
  different: { label: "Different", color: "#d97706" },
  inconclusive: { label: "Inconclusive", color: C.textMuted },
  // A settled finding, not a breakdown — hence its own label. Coloured like a
  // failure because that is what it means for the reviewer, but the step ran.
  uninhabitable: { label: "Did not activate", color: C.error },
  failed: { label: "Failed", color: C.error },
};

export function ReviewStepButton({
  stepKey,
  label,
  detail,
  icon,
  color,
  status,
  disabled = false,
  onRun,
}: {
  stepKey: ReviewStepKey;
  label: string;
  detail?: string;
  icon: ReactNode;
  color: string;
  status: ReviewStepStatus;
  disabled?: boolean;
  onRun: (step: ReviewStepKey) => void;
}) {
  const meta = STATUS_META[status];
  const active = status === "queued" || status === "running";

  return (
    <button
      type="button"
      onClick={() => onRun(stepKey)}
      aria-label={`Reproduce ${label}`}
      disabled={disabled}
      style={{
        width: 116,
        minHeight: 66,
        padding: "8px 9px",
        display: "grid",
        gridTemplateColumns: "22px 1fr",
        columnGap: 7,
        alignItems: "start",
        borderRadius: 9,
        border: `1px solid ${active ? color : C.border}`,
        background: active ? translucent(color, 5) : C.surface,
        color: C.text,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.58 : 1,
        textAlign: "left",
        boxShadow: active ? `0 0 0 2px ${translucent(color, 8.6)}` : "none",
      }}
    >
      <span style={{ color, display: "flex", paddingTop: 1 }}>{active ? Ic.loader(16) : icon}</span>
      <span style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 3 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 750,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
        {detail ? (
          <span
            style={{
              color: C.textMuted,
              fontFamily: F.mono,
              fontSize: 8.5,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {detail}
          </span>
        ) : null}
        <span style={{ color: meta.color, fontFamily: F.mono, fontSize: 8.5, fontWeight: 800 }}>
          {meta.label.toUpperCase()}
        </span>
      </span>
    </button>
  );
}

import { useEffect, useRef } from "react";
import type { Badges, LogEntry } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { CenterSealStrip } from "../pages/overview/components/CenterSealStrip";

interface SealHubPanelProps {
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  locked: boolean;
  sealed: boolean;
  sealRunning: boolean;
  sealLog: LogEntry | null;
  onSeal: (inclusionOpts: { includeSource: boolean; includeRuntime: boolean }) => void;
  onPreviewReviewer: () => void;
  onDownloadRee: () => void;
  onClose: () => void;
}

// The seal panel lives directly in the constellation hub — no docked window or
// scrim — so the surrounding pod and nodes stay visible while sealing.
export function SealHubPanel({
  ree,
  evaluation,
  badges,
  locked,
  sealed,
  sealRunning,
  sealLog,
  onSeal,
  onPreviewReviewer,
  onDownloadRee,
  onClose,
}: SealHubPanelProps) {
  const sealRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <section
      aria-label="Seal"
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 20,
        margin: "0 auto",
        zIndex: 20,
        width: "min(440px, calc(100% - 32px))",
        maxHeight: "calc(100% - 88px)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        overflowY: "auto",
        padding: "16px 18px 18px",
        background: "rgba(255,255,255,0.82)",
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        backdropFilter: "blur(8px)",
        boxShadow: "0 18px 44px rgba(13,17,23,0.16)",
        animation: "dockIn 0.3s cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          width: 28,
          height: 28,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          background: C.surface,
          color: C.textMuted,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {Ic.x(14)}
      </button>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          Seal
        </div>
        <div style={{ fontSize: 11.5, fontFamily: F.mono, color: C.textMuted, marginTop: 2 }}>
          freeze the specimen into an archivable REE
        </div>
      </div>

      <CenterSealStrip
        ree={ree}
        locked={locked}
        evaluation={evaluation}
        badges={badges}
        onSeal={onSeal}
        sealRunning={sealRunning}
        sealLog={sealLog}
        onPreviewReviewer={onPreviewReviewer}
        onDownloadRee={sealed ? onDownloadRee : undefined}
        sealRef={sealRef}
      />
    </section>
  );
}

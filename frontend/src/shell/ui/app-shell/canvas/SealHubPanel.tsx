import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { Badges, LogEntry } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { ConsistencyReport } from "@core/ree-steps/sealConsistency";
import { useRef } from "react";
import { C, F } from "../../theme/theme";
import { CenterSealStrip } from "./CenterSealStrip";
import { HubPanel } from "./HubPanel";

interface SealHubPanelProps {
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  consistency?: ConsistencyReport;
  locked: boolean;
  sealRunning: boolean;
  sealLog: LogEntry | null;
  onSeal: (inclusionOpts: InclusionOpts) => void;
  onClose: () => void;
}

// The seal panel lives directly in the constellation hub — no docked window or
// scrim — so the surrounding pod and nodes stay visible while sealing.
export function SealHubPanel({
  ree,
  evaluation,
  badges,
  consistency,
  locked,
  sealRunning,
  sealLog,
  onSeal,
  onClose,
}: SealHubPanelProps) {
  const sealRef = useRef<HTMLDivElement>(null);

  return (
    <HubPanel ariaLabel="Seal" onClose={onClose} width={440} align="center">
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
        consistency={consistency}
        onSeal={onSeal}
        sealRunning={sealRunning}
        sealLog={sealLog}
        sealRef={sealRef}
      />
    </HubPanel>
  );
}

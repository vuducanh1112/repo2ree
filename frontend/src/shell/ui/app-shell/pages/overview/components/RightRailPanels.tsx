import type React from "react";
import type { Badges, Timestamps } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import type { AppShellPage as AppShellPageType } from "../../../state/pages";
import { ExperimentsPanel } from "./ExperimentsPanel";
import { ActivationCard, ArchiveCard } from "./RightRailPanelArchiveActivation";
import { EvaluateCard, SwhCard } from "./RightRailPanelSections";

interface RightRailPanelsProps {
  ree: ReeEditorViewModel;
  badges: Badges;
  timestamps: Timestamps;
  evaluation: EvaluationState;
  onNavigate: (key: AppShellPageType) => void;
  onGoField: (key: string) => void;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
  experimentsRef: React.RefObject<HTMLDivElement>;
}

export function RightRailPanels({
  ree,
  badges,
  timestamps,
  evaluation,
  onNavigate,
  onGoField,
  swhRef,
  evaluateRef,
  archiveRef,
  activationRef,
  experimentsRef,
}: RightRailPanelsProps) {
  return (
    <div
      style={{
        width: 196,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        position: "relative",
        zIndex: 1,
      }}
    >
      <SwhCard ree={ree} onNavigate={onNavigate} swhRef={swhRef} />
      <EvaluateCard
        badges={badges}
        timestamps={timestamps}
        evaluation={evaluation}
        onNavigate={onNavigate}
        evaluateRef={evaluateRef}
      />
      <ArchiveCard ree={ree} onNavigate={onNavigate} archiveRef={archiveRef} />
      <ActivationCard
        ree={ree}
        badges={badges}
        onNavigate={onNavigate}
        onGoField={onGoField}
        activationRef={activationRef}
      />
      <ExperimentsPanel ree={ree} experimentsRef={experimentsRef} onNavigate={onNavigate} />
    </div>
  );
}

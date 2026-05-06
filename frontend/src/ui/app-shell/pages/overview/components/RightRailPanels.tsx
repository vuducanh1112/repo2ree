import type React from "react";
import type { ReeEditorViewModel } from "../../../../../application/ree-editor/reeEditorViewModel";
import type { AppShellPage as AppShellPageType } from "../../../../../application/state/pages";
import type { Badges, Timestamps } from "../../../../../core/ree/ReeTypes";
import { ActivationCard, ArchiveCard } from "./RightRailPanelArchiveActivation";
import { EvaluateCard, SwhCard } from "./RightRailPanelSections";

interface RightRailPanelsProps {
  ree: ReeEditorViewModel;
  badges: Badges;
  timestamps: Timestamps;
  level: number;
  onNavigate: (key: AppShellPageType) => void;
  onGoField: (key: string) => void;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
}

export function RightRailPanels({
  ree,
  badges,
  timestamps,
  level,
  onNavigate,
  onGoField,
  swhRef,
  evaluateRef,
  archiveRef,
  activationRef,
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
        level={level}
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
    </div>
  );
}

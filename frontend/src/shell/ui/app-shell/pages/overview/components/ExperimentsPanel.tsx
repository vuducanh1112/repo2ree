import type React from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { lgStage } from "../../../../theme/lightGlassTheme";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

interface ExperimentsPanelProps {
  ree: ReeEditorViewModel;
  experimentsRef: React.RefObject<HTMLDivElement>;
  onNavigate: (key: AppShellPage) => void;
}

const tint = lgStage.experiments;

export function ExperimentsPanel({ ree, experimentsRef, onNavigate }: ExperimentsPanelProps) {
  const experiments = ree.experiments ?? [];
  const count = experiments.length;
  const hasExperiments = count > 0;
  const withCommand = experiments.filter((e) => e.command.trim() !== "").length;

  return (
    <OverviewPanel
      panelRef={experimentsRef}
      tint={tint}
      title="Experiments"
      active={hasExperiments}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Edit Experiments"
          onClick={() => onNavigate(PAGE.EXPERIMENTS)}
        />
      }
    >
      <PanelFieldRow
        label="Defined"
        value={hasExperiments ? `${count} experiment${count !== 1 ? "s" : ""}` : null}
        filled={hasExperiments}
        emptyText="none recorded"
        tint={tint}
        onClick={() => onNavigate(PAGE.EXPERIMENTS)}
        isLast={!hasExperiments}
      />
      {hasExperiments && (
        <PanelFieldRow
          label="Runnable"
          value={`${withCommand}/${count} with command`}
          filled={withCommand > 0}
          tint={tint}
          onClick={() => onNavigate(PAGE.EXPERIMENTS)}
          isLast={true}
        />
      )}
    </OverviewPanel>
  );
}

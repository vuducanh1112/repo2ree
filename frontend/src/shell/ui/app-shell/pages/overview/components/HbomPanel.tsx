import type React from "react";
import { hbomSummaryLines } from "../../../../../../core/hbom/HbomSummary";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { lgStage } from "../../../../theme/lightGlassTheme";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

interface HbomPanelProps {
  ree: ReeEditorViewModel;
  hbomRef: React.RefObject<HTMLDivElement>;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
}

const tint = lgStage.hbom;

export function HbomPanel({ ree, hbomRef, onGoField, onNavigate }: HbomPanelProps) {
  const lines = hbomSummaryLines(ree.hardware_description);
  const hasComponents = lines.length > 0;

  return (
    <OverviewPanel
      panelRef={hbomRef}
      tint={tint}
      title="HBOM"
      active={hasComponents}
      footer={
        <OverviewNavButton tint={tint} label="Edit HBOM" onClick={() => onNavigate(PAGE.HBOM)} />
      }
    >
      <PanelFieldRow
        label="Components"
        value={hasComponents ? `${lines.length} item${lines.length !== 1 ? "s" : ""}` : null}
        filled={hasComponents}
        emptyText="not captured"
        tint={tint}
        onClick={() => onGoField("hardware_description")}
        isLast={!hasComponents}
      />
      {lines.slice(0, 3).map((line, index) => (
        <PanelFieldRow
          key={line}
          label={index === 0 ? "Preview" : " "}
          value={line}
          filled
          tint={tint}
          onClick={() => onGoField("hardware_description")}
          isLast={index === Math.min(lines.length, 3) - 1}
        />
      ))}
    </OverviewPanel>
  );
}

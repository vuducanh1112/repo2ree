import type React from "react";
import type { Badges } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { lgStage } from "../../../../theme/lightGlassTheme";
import { FIELD_META } from "../../../fieldTips/fieldMeta";
import { type AppShellPage, PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

export function ArchiveCard(props: {
  ree: ReeEditorViewModel;
  onNavigate: (key: AppShellPage) => void;
  archiveRef: React.RefObject<HTMLDivElement>;
}) {
  const tint = lgStage.archive;
  const zenodoFilled = !!props.ree.zenodo_doi && (props.ree.zenodo_doi as string).trim().length > 0;
  const dataverseFilled =
    !!props.ree.dataverse_doi && (props.ree.dataverse_doi as string).trim().length > 0;

  return (
    <OverviewPanel
      panelRef={props.archiveRef}
      tint={tint}
      title="Archival & DOIs"
      active={zenodoFilled || dataverseFilled}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Archival & DOIs"
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
        />
      }
    >
      <PanelFieldRow
        label="Zenodo"
        value={zenodoFilled ? (props.ree.zenodo_doi as string) : null}
        filled={zenodoFilled}
        emptyText="unregistered"
        tint={tint}
        onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
      />
      <PanelFieldRow
        label="Dataverse"
        value={dataverseFilled ? (props.ree.dataverse_doi as string) : null}
        filled={dataverseFilled}
        emptyText="unregistered"
        tint={tint}
        isLast
        onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
      />
    </OverviewPanel>
  );
}

export function ActivationCard(props: {
  ree: ReeEditorViewModel;
  badges: Badges;
  onNavigate: (key: AppShellPage) => void;
  onGoField: (key: string) => void;
  activationRef: React.RefObject<HTMLDivElement>;
}) {
  const tint = lgStage.activation;
  return (
    <OverviewPanel
      panelRef={props.activationRef}
      tint={tint}
      title="Test Activation"
      active={!!props.badges?.activation}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Test Activation"
          onClick={() => props.onNavigate?.(PAGE.ACTIVATION)}
        />
      }
    >
      <PanelFieldRow
        label={FIELD_META.activation_script?.label || "Activation script"}
        value={props.ree.activation_script || null}
        filled={!!props.ree.activation_script}
        tint={tint}
        isLast
        onClick={() => props.onGoField?.("activation_script")}
      />
    </OverviewPanel>
  );
}

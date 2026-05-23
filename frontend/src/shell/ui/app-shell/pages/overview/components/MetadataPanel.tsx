import type React from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { lgStage } from "../../../../theme/lightGlassTheme";
import { FIELD_META } from "../../../fieldTips/fieldMeta";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

interface MetadataPanelProps {
  ree: ReeEditorViewModel;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
  metadataRef: React.RefObject<HTMLDivElement>;
}

const tint = lgStage.metadata;

export function MetadataPanel({ ree, onGoField, onNavigate, metadataRef }: MetadataPanelProps) {
  const metadataFields = ["name"] as (keyof ReeEditorViewModel)[];
  const filledCount = metadataFields.filter((field) => !!ree[field]).length;

  return (
    <OverviewPanel
      panelRef={metadataRef}
      tint={tint}
      title="Metadata"
      active={filledCount > 0}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Edit Metadata"
          onClick={() => onNavigate(PAGE.METADATA)}
        />
      }
    >
      {metadataFields.map((field, index) => {
        const rawValue = ree[field];
        const filled = !!rawValue;
        const label = FIELD_META[field as string]?.label || String(field);
        const displayValue = String(rawValue ?? "");

        return (
          <PanelFieldRow
            key={field}
            label={label}
            value={filled ? displayValue : null}
            filled={filled}
            tint={tint}
            isLast={index === metadataFields.length - 1}
            onClick={() => onGoField(String(field))}
          />
        );
      })}
    </OverviewPanel>
  );
}

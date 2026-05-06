import type React from "react";
import type { ReeEditorViewModel } from "../../../../../application/ree-editor/reeEditorViewModel";
import { FIELD_META } from "../../../../../application/state/fieldMeta";
import { type AppShellPage, PAGE } from "../../../../../application/state/pages";
import type { Badges } from "../../../../../core/ree/ReeTypes";
import {
  C,
  hoverBrightness,
  S_OVERVIEW_PANEL_BADGE_BASE,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_FOOTER,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_PANEL_HEADER_LABEL,
} from "../../../../theme/theme";
import { PanelFieldRow } from "./PanelFieldRow";

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  background: C.surface,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  ...extra,
});

export function ArchiveCard(props: {
  ree: ReeEditorViewModel;
  onNavigate: (key: AppShellPage) => void;
  archiveRef: React.RefObject<HTMLDivElement>;
}) {
  return (
    <div ref={props.archiveRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#059669",
            boxShadow:
              props.ree.zenodo_doi || props.ree.dataverse_doi ? "0 0 5px #05966999" : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Archival & DOIs</span>
      </div>
      <div style={S_OVERVIEW_PANEL_FIELDS}>
        <PanelFieldRow
          label="Zenodo"
          value={props.ree.zenodo_doi ? (props.ree.zenodo_doi as string) : null}
          filled={!!props.ree.zenodo_doi && (props.ree.zenodo_doi as string).trim().length > 0}
          emptyText="unregistered"
          dotColor="#059669"
          dotGlow="#05966999"
          labelColor="#065f46"
          labelBg="#f0fdf4"
          labelBorderColor="#05966925"
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
        />
        <PanelFieldRow
          label="Dataverse"
          value={props.ree.dataverse_doi ? (props.ree.dataverse_doi as string) : null}
          filled={
            !!props.ree.dataverse_doi && (props.ree.dataverse_doi as string).trim().length > 0
          }
          emptyText="unregistered"
          dotColor="#059669"
          dotGlow="#05966999"
          labelColor="#065f46"
          labelBg="#f0fdf4"
          labelBorderColor="#05966925"
          isLast
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
        />
      </div>
      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#065f46",
            background: "#f0fdf4",
            border: "1px solid #a7f3d0",
          }}
          {...hoverBrightness(95)}
        >
          → Go to Archival & DOIs
        </button>
      </div>
    </div>
  );
}

export function ActivationCard(props: {
  ree: ReeEditorViewModel;
  badges: Badges;
  onNavigate: (key: AppShellPage) => void;
  onGoField: (key: string) => void;
  activationRef: React.RefObject<HTMLDivElement>;
}) {
  return (
    <div ref={props.activationRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#7c3aed",
            boxShadow: props.badges?.activation ? "0 0 5px #7c3aed99" : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Test Activation</span>
        {props.badges?.activation && (
          <span
            style={{
              ...S_OVERVIEW_PANEL_BADGE_BASE,
              color: "#7c3aed",
              background: "#f5f3ff",
              border: "1px solid #7c3aed40",
            }}
          >
            OK
          </span>
        )}
      </div>
      <PanelFieldRow
        label={FIELD_META.activation_script?.label || "Activation script"}
        value={props.ree.activation_script || null}
        filled={!!props.ree.activation_script}
        dotColor="#7c3aed"
        dotGlow="#7c3aed99"
        labelColor="#5b21b6"
        labelBg="#f5f3ff"
        labelBorderColor="#7c3aed25"
        isLast
        onClick={() => props.onGoField?.("activation_script")}
      />
      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => props.onNavigate?.(PAGE.ACTIVATION)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#7c3aed",
            background: "#f5f3ff",
            border: "1px solid #7c3aed40",
          }}
          {...hoverBrightness(95)}
        >
          → Go to Test Activation
        </button>
      </div>
    </div>
  );
}

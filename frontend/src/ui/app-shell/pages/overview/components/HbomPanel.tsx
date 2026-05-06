import type React from "react";
import { hbomSummaryLines } from "../../../../../core/hbom/HbomSummary";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import type { AppShellPage } from "../../../../../shell/ui/app-shell/state/pages";
import { PAGE } from "../../../../../shell/ui/app-shell/state/pages";
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

interface HbomPanelProps {
  ree: ReeEditorViewModel;
  hbomRef: React.RefObject<HTMLDivElement>;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
}

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  background: C.surface,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  ...extra,
});

export function HbomPanel({ ree, hbomRef, onGoField, onNavigate }: HbomPanelProps) {
  const lines = hbomSummaryLines(ree.hardware_description);

  return (
    <div ref={hbomRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#0f766e",
            boxShadow: lines.length > 0 ? "0 0 5px #0f766e99" : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>HBOM</span>
        {lines.length > 0 && (
          <span
            style={{
              ...S_OVERVIEW_PANEL_BADGE_BASE,
              color: "#0f766e",
              background: "#ecfeff",
              border: "1px solid #99f6e4",
            }}
          >
            HW
          </span>
        )}
      </div>

      <div style={S_OVERVIEW_PANEL_FIELDS}>
        <PanelFieldRow
          label="Components"
          value={lines.length > 0 ? `${lines.length} item${lines.length !== 1 ? "s" : ""}` : null}
          filled={lines.length > 0}
          emptyText="not captured"
          dotColor="#0f766e"
          dotGlow="#0f766e99"
          labelColor="#115e59"
          labelBg="#ecfeff"
          labelBorderColor="#0f766e25"
          onClick={() => onGoField("hardware_description")}
          isLast={lines.length === 0}
        />
        {lines.slice(0, 3).map((line, index) => (
          <PanelFieldRow
            key={line}
            label={index === 0 ? "Preview" : " "}
            value={line}
            filled
            dotColor="#0f766e"
            dotGlow="#0f766e99"
            labelColor="#115e59"
            labelBg="#ecfeff"
            labelBorderColor="#0f766e25"
            onClick={() => onGoField("hardware_description")}
            isLast={index === Math.min(lines.length, 3) - 1}
          />
        ))}
      </div>

      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => onNavigate(PAGE.HBOM)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#115e59",
            background: "#ecfeff",
            border: "1px solid #99f6e4",
          }}
          {...hoverBrightness(95)}
        >
          → Edit HBOM
        </button>
      </div>
    </div>
  );
}

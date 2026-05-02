import type React from "react";
import type { AppShellPage } from "../../../../../application/app-shell/AppShellPages";
import { PAGE } from "../../../../../application/app-shell/AppShellPages";
import { FIELD_META } from "../../../../../application/app-shell/fieldMeta";
import type { ReeDraftViewModel } from "../../../../../domain/ree/ReeSpec";
import {
  C,
  F,
  hoverBrightness,
  S_OVERVIEW_META_FOOTER,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_PANEL_HEADER_LABEL,
} from "../../../../theme/theme";
import { PanelFieldRow } from "./PanelFieldRow";

interface MetadataPanelProps {
  ree: ReeDraftViewModel;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
  metadataRef: React.RefObject<HTMLDivElement>;
}

export function MetadataPanel({ ree, onGoField, onNavigate, metadataRef }: MetadataPanelProps) {
  const metadataFields = ["name"] as (keyof ReeDraftViewModel)[];
  const filledCount = metadataFields.filter((field) => !!ree[field]).length;

  return (
    <div
      ref={metadataRef}
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e" }} />
        <span style={S_PANEL_HEADER_LABEL}>Metadata</span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 8,
            fontFamily: F.mono,
            color: C.textMuted,
            letterSpacing: 0.5,
          }}
        >
          {filledCount}/2
        </span>
      </div>
      <div style={S_OVERVIEW_PANEL_FIELDS}>
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
              dotColor="#22c55e"
              dotGlow="#22c55e99"
              labelColor="#15803d"
              labelBg="#f0fdf4"
              labelBorderColor="#22c55e25"
              isLast={index === metadataFields.length - 1}
              onClick={() => onGoField(String(field))}
            />
          );
        })}
      </div>
      <div style={S_OVERVIEW_META_FOOTER}>
        <button
          type="button"
          onClick={() => onNavigate(PAGE.METADATA)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: C.text,
            background: "#f0fdf4",
            border: `1px solid ${C.border}40`,
            marginTop: 2,
          }}
          {...hoverBrightness(95)}
        >
          → Edit Metadata
        </button>
      </div>
    </div>
  );
}

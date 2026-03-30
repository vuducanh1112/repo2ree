import type React from "react";
import { FIELD_META } from "../../../constants/fieldMeta";
import { PAGE } from "../../../constants/pages";
import {
  C,
  F,
  hoverBrightness,
  S_OVERVIEW_META_FOOTER,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_PANEL_HEADER_LABEL,
} from "../../../constants/theme";
import type { ExplorerPage, Ree } from "../../../types";
import { PanelFieldRow } from "./PanelFieldRow";

interface MetadataPanelProps {
  ree: Ree;
  onGoField: (key: string) => void;
  onNavigate: (key: ExplorerPage) => void;
  metadataRef: React.RefObject<HTMLDivElement>;
}

export function MetadataPanel({ ree, onGoField, onNavigate, metadataRef }: MetadataPanelProps) {
  const metadataFields = ["name", "hardware_description"] as (keyof Ree)[];
  const filledCount = metadataFields.filter((field) =>
    field === "hardware_description"
      ? Object.values((ree[field] as Record<string, string>) || {}).some((value) => value)
      : !!ree[field],
  ).length;

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
          const isHardware = field === "hardware_description";
          const rawValue = ree[field];
          const filled = isHardware
            ? Object.values((rawValue as Record<string, string>) || {}).some((value) => value)
            : !!rawValue;
          const label =
            FIELD_META[field as string]?.label || (isHardware ? "Hardware" : String(field));
          const displayValue = isHardware
            ? Object.entries((rawValue as Record<string, string>) || {})
                .filter(([, value]) => value)
                .map(([key, value]) => `${key}: ${value}`)
                .join(", ")
            : String(rawValue ?? "");

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

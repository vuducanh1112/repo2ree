import type React from "react";
import { REE_ASSEMBLY_STEPS } from "../../../../../application/ree-assembly/assemblyCatalog";
import type { ReeEditorViewModel } from "../../../../../application/ree-editor/reeEditorViewModel";
import {
  type AppShellPage,
  isValidAppShellPage,
  PAGE,
} from "../../../../../application/state/pages";
import type { Badges, Timestamps } from "../../../../../domain/ree/ReeTypes";
import { LEVELS } from "../../../../../domain/review/levels";
import { Ic } from "../../../../shared/components/Icon";
import {
  C,
  F,
  hoverBrightness,
  S_FLEX_ROW_CENTER_GAP_6,
  S_OVERVIEW_META_FOOTER,
  S_OVERVIEW_PANEL_BADGE_BASE,
  S_OVERVIEW_PANEL_BUTTON_BASE,
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

export function SwhCard(props: {
  ree: ReeEditorViewModel;
  onNavigate: (key: AppShellPage) => void;
  swhRef: React.RefObject<HTMLDivElement>;
}) {
  return (
    <div ref={props.swhRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#e4572e",
            boxShadow: props.ree.swhid ? "0 0 5px #e4572e99" : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Software Heritage</span>
        <span
          style={{
            ...S_OVERVIEW_PANEL_BADGE_BASE,
            color: "#e4572e",
            background: "#fff7f5",
            border: "1px solid #fbd0c4",
          }}
        >
          SWH
        </span>
      </div>
      <PanelFieldRow
        label="SWHID"
        value={props.ree.swhid || null}
        filled={!!props.ree.swhid}
        dotColor="#e4572e"
        dotGlow="#e4572e99"
        labelColor="#9a3412"
        labelBg="#fff7f5"
        labelBorderColor="#e4572e25"
        emptyText="not archived"
        isLast
        onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
      />
      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#9a3412",
            background: "#fff7f5",
            border: "1px solid #fbd0c4",
          }}
          {...hoverBrightness(95)}
        >
          → Go to Software Heritage
        </button>
      </div>
    </div>
  );
}

export function EvaluateCard(props: {
  badges: Badges;
  timestamps: Timestamps;
  level: number;
  onNavigate: (key: AppShellPage) => void;
  evaluateRef: React.RefObject<HTMLDivElement>;
}) {
  const assemblyStep = REE_ASSEMBLY_STEPS.find(
    (assemblyStep) => assemblyStep.key === PAGE.EVALUATE,
  );
  if (!assemblyStep) return null;

  const evaluateDate = props.timestamps[assemblyStep.key]
    ? new Date(props.timestamps[assemblyStep.key]).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;
  const earned = !!props.badges[assemblyStep.key];

  return (
    <div ref={props.evaluateRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: earned ? assemblyStep.badge.color : "#d1d5db",
            boxShadow: earned ? `0 0 5px ${assemblyStep.badge.color}99` : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Evaluate</span>
        {earned && (
          <span
            style={{
              ...S_OVERVIEW_PANEL_BADGE_BASE,
              color: assemblyStep.badge.color,
              background: assemblyStep.badge.bg,
              border: `1px solid ${assemblyStep.badge.color}40`,
            }}
          >
            OK
          </span>
        )}
      </div>
      <div style={S_OVERVIEW_META_FOOTER}>
        <div style={S_FLEX_ROW_CENTER_GAP_6}>
          <span style={{ display: "flex", color: earned ? assemblyStep.badge.color : C.textMuted }}>
            {Ic.star(12)}
          </span>
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              color: earned ? C.text : C.textMuted,
              flex: 1,
            }}
          >
            {earned
              ? `L${props.level} — ${LEVELS[Math.min(props.level, 7)].label}`
              : "Not evaluated"}
          </span>
        </div>
        {earned && evaluateDate && (
          <div style={{ fontSize: 9, fontFamily: F.mono, color: C.textMuted, letterSpacing: 0.2 }}>
            {evaluateDate}
          </div>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "5px 8px",
            borderRadius: 5,
            background: earned ? assemblyStep.badge.bg : C.surfaceAlt,
            border: `1px solid ${earned ? `${assemblyStep.badge.color}40` : C.border}`,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              color: earned ? assemblyStep.badge.color : C.textMuted,
              fontWeight: 600,
            }}
          >
            {earned ? "✓ score computed" : "run Evaluate"}
          </span>
        </div>
        <button
          type="button"
          onClick={() =>
            props.onNavigate?.(
              isValidAppShellPage(assemblyStep.key)
                ? (assemblyStep.key as AppShellPage)
                : PAGE.OVERVIEW,
            )
          }
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: assemblyStep.badge.color,
            background: assemblyStep.badge.bg,
            border: `1px solid ${assemblyStep.badge.color}40`,
          }}
          {...hoverBrightness(95)}
        >
          → Go to Evaluate
        </button>
      </div>
    </div>
  );
}

import type React from "react";
import type { Badges, Timestamps } from "../../../../../../core/ree/ReeTypes";
import { REE_ASSEMBLY_STEPS } from "../../../../../../core/ree-assembly/assemblyCatalog";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { Ic } from "../../../../shared/components/Icon";
import { lgBackgrounds, lgColors, lgStage } from "../../../../theme/lightGlassTheme";
import { F, S_FLEX_ROW_CENTER_GAP_6 } from "../../../../theme/theme";
import { type AppShellPage, isValidAppShellPage, PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

export function SwhCard(props: {
  ree: ReeEditorViewModel;
  onNavigate: (key: AppShellPage) => void;
  swhRef: React.RefObject<HTMLDivElement>;
}) {
  const tint = lgStage.swh;
  return (
    <OverviewPanel
      panelRef={props.swhRef}
      tint={tint}
      title="Software Heritage"
      active={!!props.ree.swhid}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Software Heritage"
          onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
        />
      }
    >
      <PanelFieldRow
        label="SWHID"
        value={props.ree.swhid || null}
        filled={!!props.ree.swhid}
        tint={tint}
        emptyText="not archived"
        isLast
        onClick={() => props.onNavigate?.(PAGE.ARCHIVE)}
      />
    </OverviewPanel>
  );
}

export function EvaluateCard(props: {
  badges: Badges;
  timestamps: Timestamps;
  evaluation: EvaluationState;
  onNavigate: (key: AppShellPage) => void;
  evaluateRef: React.RefObject<HTMLDivElement>;
}) {
  const assemblyStep = REE_ASSEMBLY_STEPS.find(
    (assemblyStep) => assemblyStep.key === PAGE.EVALUATE,
  );
  if (!assemblyStep) return null;

  const tint = lgStage.evaluate;
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
    <OverviewPanel
      panelRef={props.evaluateRef}
      tint={tint}
      title="Evaluate"
      active={earned}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Evaluate"
          onClick={() =>
            props.onNavigate?.(
              isValidAppShellPage(assemblyStep.key)
                ? (assemblyStep.key as AppShellPage)
                : PAGE.OVERVIEW,
            )
          }
        />
      }
    >
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
        <div style={S_FLEX_ROW_CENTER_GAP_6}>
          <span style={{ display: "flex", color: earned ? tint.line : lgColors.textMuted }}>
            {Ic.star(12)}
          </span>
          <span
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              color: earned ? lgColors.text : lgColors.textMuted,
              flex: 1,
            }}
          >
            {earned ? standingMeta(props.evaluation).label : "Not evaluated"}
          </span>
        </div>
        {earned && evaluateDate && (
          <div
            style={{
              fontSize: 9,
              fontFamily: F.mono,
              color: lgColors.textMuted,
              letterSpacing: 0.2,
            }}
          >
            {evaluateDate}
          </div>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "5px 9px",
            borderRadius: 6,
            background: earned ? tint.bg : lgBackgrounds.disabled,
            border: `1px solid ${earned ? tint.border : "rgba(148, 163, 184, 0.34)"}`,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              color: earned ? tint.ink : lgColors.textMuted,
              fontWeight: 700,
            }}
          >
            {earned ? "✓ score computed" : "run Evaluate"}
          </span>
        </div>
      </div>
    </OverviewPanel>
  );
}

import type React from "react";
import type { AppShellPage as AppShellPageType } from "../../../../../application/app-shell/AppShellPages";
import {
  type AppShellPage,
  isValidAppShellPage,
  PAGE,
} from "../../../../../application/app-shell/AppShellPages";
import { FIELD_META } from "../../../../../application/app-shell/fieldMeta";
import { AUTOMATION_STEPS } from "../../../../../application/workflow/workflowCatalog";
import type { ReeDraftViewModel } from "../../../../../domain/ree/ReeSpec";
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
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_FOOTER,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_PANEL_HEADER_LABEL,
} from "../../../../theme/theme";
import { PanelFieldRow } from "./PanelFieldRow";

interface RightRailPanelsProps {
  ree: ReeDraftViewModel;
  badges: Badges;
  timestamps: Timestamps;
  level: number;
  onNavigate: (key: AppShellPageType) => void;
  onGoField: (key: string) => void;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
}

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...{
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
  },
  ...extra,
});

export function RightRailPanels({
  ree,
  badges,
  timestamps,
  level,
  onNavigate,
  onGoField,
  swhRef,
  evaluateRef,
  archiveRef,
  activationRef,
}: RightRailPanelsProps) {
  const workflowStep = AUTOMATION_STEPS.find((workflow) => workflow.key === PAGE.EVALUATE);
  const evaluateDate =
    workflowStep && timestamps[workflowStep.key]
      ? new Date(timestamps[workflowStep.key]).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;

  return (
    <div
      style={{
        width: 196,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        position: "relative",
        zIndex: 1,
      }}
    >
      <div ref={swhRef} style={panel({ overflow: "hidden" })}>
        <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
          <div
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#e4572e",
              boxShadow: ree.swhid ? "0 0 5px #e4572e99" : "none",
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
          value={ree.swhid || null}
          filled={!!ree.swhid}
          dotColor="#e4572e"
          dotGlow="#e4572e99"
          labelColor="#9a3412"
          labelBg="#fff7f5"
          labelBorderColor="#e4572e25"
          emptyText="not archived"
          isLast
          onClick={() => onNavigate?.(PAGE.ARCHIVE)}
        />
        <div style={S_OVERVIEW_PANEL_FOOTER}>
          <button
            type="button"
            onClick={() => onNavigate?.(PAGE.ARCHIVE)}
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

      {workflowStep &&
        (() => {
          const earned = !!badges[workflowStep.key];
          return (
            <div ref={evaluateRef} style={panel({ overflow: "hidden" })}>
              <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
                <div
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: earned ? workflowStep.badge.color : "#d1d5db",
                    boxShadow: earned ? `0 0 5px ${workflowStep.badge.color}99` : "none",
                  }}
                />
                <span style={S_PANEL_HEADER_LABEL}>Evaluate</span>
                {earned && (
                  <span
                    style={{
                      ...S_OVERVIEW_PANEL_BADGE_BASE,
                      color: workflowStep.badge.color,
                      background: workflowStep.badge.bg,
                      border: `1px solid ${workflowStep.badge.color}40`,
                    }}
                  >
                    OK
                  </span>
                )}
              </div>
              <div style={S_OVERVIEW_META_FOOTER}>
                <div style={S_FLEX_ROW_CENTER_GAP_6}>
                  <span
                    style={{
                      display: "flex",
                      color: earned ? workflowStep.badge.color : C.textMuted,
                    }}
                  >
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
                    {earned ? `L${level} — ${LEVELS[Math.min(level, 7)].label}` : "Not evaluated"}
                  </span>
                </div>
                {earned && evaluateDate && (
                  <div
                    style={{
                      fontSize: 9,
                      fontFamily: F.mono,
                      color: C.textMuted,
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
                    padding: "5px 8px",
                    borderRadius: 5,
                    background: earned ? workflowStep.badge.bg : C.surfaceAlt,
                    border: `1px solid ${earned ? `${workflowStep.badge.color}40` : C.border}`,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      color: earned ? workflowStep.badge.color : C.textMuted,
                      fontWeight: 600,
                    }}
                  >
                    {earned ? "✓ score computed" : "run Evaluate"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    onNavigate?.(
                      isValidAppShellPage(workflowStep.key)
                        ? (workflowStep.key as AppShellPage)
                        : PAGE.OVERVIEW,
                    )
                  }
                  style={{
                    ...S_OVERVIEW_PANEL_BUTTON_BASE,
                    color: workflowStep.badge.color,
                    background: workflowStep.badge.bg,
                    border: `1px solid ${workflowStep.badge.color}40`,
                  }}
                  {...hoverBrightness(95)}
                >
                  → Go to Evaluate
                </button>
              </div>
            </div>
          );
        })()}

      <div ref={archiveRef} style={panel({ overflow: "hidden" })}>
        <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
          <div
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#059669",
              boxShadow: ree.zenodo_doi || ree.dataverse_doi ? "0 0 5px #05966999" : "none",
            }}
          />
          <span style={S_PANEL_HEADER_LABEL}>Archival & DOIs</span>
        </div>
        <div style={S_OVERVIEW_PANEL_FIELDS}>
          <PanelFieldRow
            label="Zenodo"
            value={ree.zenodo_doi ? (ree.zenodo_doi as string) : null}
            filled={!!ree.zenodo_doi && (ree.zenodo_doi as string).trim().length > 0}
            emptyText="unregistered"
            dotColor="#059669"
            dotGlow="#05966999"
            labelColor="#065f46"
            labelBg="#f0fdf4"
            labelBorderColor="#05966925"
            onClick={() => onNavigate?.(PAGE.ARCHIVE)}
          />
          <PanelFieldRow
            label="Dataverse"
            value={ree.dataverse_doi ? (ree.dataverse_doi as string) : null}
            filled={!!ree.dataverse_doi && (ree.dataverse_doi as string).trim().length > 0}
            emptyText="unregistered"
            dotColor="#059669"
            dotGlow="#05966999"
            labelColor="#065f46"
            labelBg="#f0fdf4"
            labelBorderColor="#05966925"
            isLast
            onClick={() => onNavigate?.(PAGE.ARCHIVE)}
          />
        </div>
        <div style={S_OVERVIEW_PANEL_FOOTER}>
          <button
            type="button"
            onClick={() => onNavigate?.(PAGE.ARCHIVE)}
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

      <div ref={activationRef} style={panel({ overflow: "hidden" })}>
        <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
          <div
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#7c3aed",
              boxShadow: badges?.activation ? "0 0 5px #7c3aed99" : "none",
            }}
          />
          <span style={S_PANEL_HEADER_LABEL}>Test Activation</span>
          {badges?.activation && (
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
          value={ree.activation_script || null}
          filled={!!ree.activation_script}
          dotColor="#7c3aed"
          dotGlow="#7c3aed99"
          labelColor="#5b21b6"
          labelBg="#f5f3ff"
          labelBorderColor="#7c3aed25"
          isLast
          onClick={() => onGoField?.("activation_script")}
        />
        <div style={S_OVERVIEW_PANEL_FOOTER}>
          <button
            type="button"
            onClick={() => onNavigate?.(PAGE.ACTIVATION)}
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
    </div>
  );
}

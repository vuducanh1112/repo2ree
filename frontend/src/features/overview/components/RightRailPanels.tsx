import type React from "react";
import { Ic } from "../../../components/Icon";
import { FIELD_META } from "../../../constants/fieldMeta";
import { LEVELS } from "../../../constants/levels";
import {
  isValidWorkspaceEditorPage,
  PAGE,
  type WorkspaceEditorPage,
} from "../../../constants/pages";
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
} from "../../../constants/theme";
import { AUTOMATION_STEPS } from "../../../constants/workflowSteps";
import type {
  Badges,
  Ree,
  Timestamps,
  WorkspaceEditorPage as WorkspaceEditorPageType,
} from "../../../types";
import { PanelFieldRow } from "./PanelFieldRow";

interface RightRailPanelsProps {
  ree: Ree;
  badges: Badges;
  timestamps: Timestamps;
  level: number;
  onNavigate: (key: WorkspaceEditorPageType) => void;
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
  const service = AUTOMATION_STEPS.find((svc) => svc.key === PAGE.EVALUATE);
  const evaluateDate =
    service && timestamps[service.key]
      ? new Date(timestamps[service.key]).toLocaleString([], {
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

      {service &&
        (() => {
          const earned = !!badges[service.key];
          return (
            <div ref={evaluateRef} style={panel({ overflow: "hidden" })}>
              <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
                <div
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: earned ? service.badge.color : "#d1d5db",
                    boxShadow: earned ? `0 0 5px ${service.badge.color}99` : "none",
                  }}
                />
                <span style={S_PANEL_HEADER_LABEL}>Evaluate</span>
                {earned && (
                  <span
                    style={{
                      ...S_OVERVIEW_PANEL_BADGE_BASE,
                      color: service.badge.color,
                      background: service.badge.bg,
                      border: `1px solid ${service.badge.color}40`,
                    }}
                  >
                    OK
                  </span>
                )}
              </div>
              <div style={S_OVERVIEW_META_FOOTER}>
                <div style={S_FLEX_ROW_CENTER_GAP_6}>
                  <span
                    style={{ display: "flex", color: earned ? service.badge.color : C.textMuted }}
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
                    background: earned ? service.badge.bg : C.surfaceAlt,
                    border: `1px solid ${earned ? `${service.badge.color}40` : C.border}`,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.sans,
                      color: earned ? service.badge.color : C.textMuted,
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
                      isValidWorkspaceEditorPage(service.key)
                        ? (service.key as WorkspaceEditorPage)
                        : PAGE.OVERVIEW,
                    )
                  }
                  style={{
                    ...S_OVERVIEW_PANEL_BUTTON_BASE,
                    color: service.badge.color,
                    background: service.badge.bg,
                    border: `1px solid ${service.badge.color}40`,
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

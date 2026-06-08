import React from "react";
import type { ArtifactStatus } from "../../../../../core/artifact/ArtifactStatus";
import type { InclusionOpts } from "../../../../../core/ree/InclusionOpts";
import type { Badges, LogEntry, Timestamps } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import {
  axisFraction,
  axisStandings,
  axisStepLabel,
  standingMeta,
} from "../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../core/review/EvaluationState";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import type { WorkspaceSourceState } from "../../../../../core/workspace/WorkspaceSourceState";
import { Ic } from "../../../shared/components/Icon";
import { fmtBytes } from "../../../shared/formatting";
import { lgColors, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import type { AppShellPage } from "../../state/pages";
import { AllFieldsPanel } from "./components/AllFieldsPanel";
import { CenterSealStrip } from "./components/CenterSealStrip";
import { buildSealCableItems } from "./components/CenterSealStrip/helpers";
import { HbomPanel } from "./components/HbomPanel";
import { MetadataPanel } from "./components/MetadataPanel";
import { RightRailPanels } from "./components/RightRailPanels";
import { RuntimePanel } from "./components/RuntimePanel";
import { SbomPanel } from "./components/SbomPanel";
import { SourcePanel } from "./components/SourcePanel";
import { PanelCableOverlay } from "./PanelCableOverlay";
import { PodWidget } from "./PodWidget";

function OverviewReadinessMeter({
  live,
  total,
  color,
}: {
  live: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? Math.round((live / total) * 100) : 0;
  const sealable = live === total;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 168, flexShrink: 0 }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 8,
          fontFamily: F.sans,
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 800, color: lgColors.text }}>
          {sealable ? "Ready to seal" : "Readiness"}
        </span>
        <span style={{ fontSize: 11, fontFamily: F.mono, color: lgColors.textMuted }}>
          {live}/{total} connected
        </span>
      </div>
      <div style={lgStyles.progressTrack}>
        <div
          style={{
            ...lgStyles.progressFill,
            width: `${pct}%`,
            background: color,
            boxShadow: `0 0 14px ${color}55`,
          }}
        />
      </div>
    </div>
  );
}

export function OverviewHeader({
  ree,
  evaluation,
  badges,
}: {
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
}) {
  const levelMeta = standingMeta(evaluation);
  const cableItems = buildSealCableItems(ree, badges);
  const live = cableItems.filter((item) => item.live).length;

  return (
    <GlassPageHeader
      icon={Ic.grid(24)}
      title="Overview"
      subtitle="Reproducible Execution Environment — connect every stage to the specimen, then seal."
      badges={
        <>
          <span
            style={{
              fontSize: 12,
              fontFamily: F.mono,
              fontWeight: 700,
              color: lgColors.primaryDeep,
              background: "rgba(239, 246, 255, 0.82)",
              border: "1px solid rgba(125, 211, 252, 0.58)",
              borderRadius: 6,
              padding: "3px 9px",
            }}
          >
            {ree.name || "untitled-env"}
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "3px 9px",
              borderRadius: 99,
              letterSpacing: 0.6,
              textTransform: "uppercase",
              background: `${levelMeta.color}16`,
              color: levelMeta.color,
              border: `1px solid ${levelMeta.color}40`,
            }}
          >
            {levelMeta.label}
          </span>
        </>
      }
      right={
        <OverviewReadinessMeter live={live} total={cableItems.length} color={levelMeta.color} />
      }
    />
  );
}

interface OverviewColumnsProps {
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  timestamps: Timestamps;
  files: FileTreeNode[];
  fileCount: number;
  totalBytes: number;
  locked: boolean;
  podSize: number;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
  onArtifactStatusChange: React.Dispatch<React.SetStateAction<ArtifactStatus>>;
  onSeal: (inclusionOpts: InclusionOpts) => void;
  sealRunning?: boolean;
  sealLog?: LogEntry | null;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
  onReleaseWorkbench?: () => void;
  refs: {
    cableContainerRef: React.RefObject<HTMLDivElement>;
    sourceRef: React.RefObject<HTMLDivElement>;
    runtimeRef: React.RefObject<HTMLDivElement>;
    leftPanelRef: React.RefObject<HTMLDivElement>;
    hbomRef: React.RefObject<HTMLDivElement>;
    swhRef: React.RefObject<HTMLDivElement>;
    evaluateRef: React.RefObject<HTMLDivElement>;
    sbomRef: React.RefObject<HTMLDivElement>;
    sealRef: React.RefObject<HTMLDivElement>;
    archiveRef: React.RefObject<HTMLDivElement>;
    activationRef: React.RefObject<HTMLDivElement>;
    experimentsRef: React.RefObject<HTMLDivElement>;
    podSvgRef: React.RefObject<SVGSVGElement>;
    podColumnRef: React.RefObject<HTMLDivElement>;
  };
}

export function OverviewColumns(props: OverviewColumnsProps) {
  const { refs } = props;
  return (
    <div
      ref={refs.cableContainerRef}
      style={{ display: "flex", alignItems: "flex-start", gap: 18, position: "relative" }}
    >
      <PanelCableOverlay
        containerRef={refs.cableContainerRef}
        sourceRef={refs.sourceRef}
        runtimeRef={refs.runtimeRef}
        metadataRef={refs.leftPanelRef}
        hbomRef={refs.hbomRef}
        swhRef={refs.swhRef}
        evaluateRef={refs.evaluateRef}
        sbomRef={refs.sbomRef}
        sealRef={refs.sealRef}
        archiveRef={refs.archiveRef}
        activationRef={refs.activationRef}
        experimentsRef={refs.experimentsRef}
        podSvgRef={refs.podSvgRef}
        evaluation={props.evaluation}
        badges={props.badges}
        ree={props.ree}
      />

      <div
        style={{
          width: 196,
          flexShrink: 0,
          position: "relative",
          zIndex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <SourcePanel
          ree={props.ree}
          sourceRef={refs.sourceRef}
          fileCount={props.fileCount}
          fileSummary={`${props.fileCount} file${props.fileCount !== 1 ? "s" : ""} · ${fmtBytes(props.totalBytes)}`}
          onGoField={props.onGoField}
          onNavigate={props.onNavigate}
        />

        <MetadataPanel
          ree={props.ree}
          onGoField={props.onGoField}
          onNavigate={props.onNavigate}
          metadataRef={refs.leftPanelRef}
        />

        <HbomPanel
          ree={props.ree}
          hbomRef={refs.hbomRef}
          onGoField={props.onGoField}
          onNavigate={props.onNavigate}
        />

        <RuntimePanel
          ree={props.ree}
          files={props.files}
          runtimeRef={refs.runtimeRef}
          onGoField={props.onGoField}
          onNavigate={props.onNavigate}
        />

        <SbomPanel
          ree={props.ree}
          files={props.files}
          badges={props.badges}
          sbomRef={refs.sbomRef}
          onNavigate={props.onNavigate}
        />
      </div>

      <div
        ref={refs.podColumnRef}
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          minWidth: 0,
          position: "relative",
          zIndex: 1,
        }}
      >
        <PodWidget evaluation={props.evaluation} svgRef={refs.podSvgRef} size={props.podSize} />

        <CenterSealStrip
          ree={props.ree}
          locked={props.locked}
          evaluation={props.evaluation}
          badges={props.badges}
          onSeal={props.onSeal}
          sealRunning={props.sealRunning}
          sealLog={props.sealLog}
          onPreviewReviewer={props.onPreviewReviewer}
          onDownloadRee={props.onDownloadRee}
          onReleaseWorkbench={props.onReleaseWorkbench}
          sealRef={refs.sealRef}
        />
      </div>

      <RightRailPanels
        ree={props.ree}
        badges={props.badges}
        timestamps={props.timestamps}
        evaluation={props.evaluation}
        onNavigate={props.onNavigate}
        onGoField={props.onGoField}
        swhRef={refs.swhRef}
        evaluateRef={refs.evaluateRef}
        archiveRef={refs.archiveRef}
        activationRef={refs.activationRef}
        experimentsRef={refs.experimentsRef}
      />
    </div>
  );
}

export function OverviewLevelStrip({ evaluation }: { evaluation: EvaluationState }) {
  return (
    <div style={{ ...lgStyles.overviewPanel, marginTop: 20, padding: "16px 20px" }}>
      <div style={{ ...lgStyles.overviewLabel, marginBottom: 14 }}>Reproducibility Axes</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {axisStandings(evaluation).map(({ axis, level }) => (
          <div key={axis.key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 800,
                fontFamily: F.sans,
                color: lgColors.text,
                width: 96,
                flexShrink: 0,
              }}
            >
              {axis.label}
            </span>
            <div style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
              {axis.steps.map((stepLabel, i) => {
                const reached = i <= level;
                const isCurrent = i === level;
                const isLast = i === axis.steps.length - 1;
                return (
                  <React.Fragment key={stepLabel}>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 5,
                      }}
                    >
                      <div
                        style={{
                          width: isCurrent ? 14 : 9,
                          height: isCurrent ? 14 : 9,
                          borderRadius: "50%",
                          background: reached ? axis.color : "rgba(148, 163, 184, 0.4)",
                          border: isCurrent ? `2.5px solid ${axis.color}` : "none",
                          boxShadow: isCurrent ? `0 0 0 4px ${axis.color}22` : "none",
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: isCurrent ? 700 : 400,
                          color: isCurrent
                            ? lgColors.text
                            : reached
                              ? lgColors.textMid
                              : lgColors.textMuted,
                          fontFamily: F.sans,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {stepLabel}
                      </span>
                    </div>
                    {!isLast && (
                      <div
                        style={{
                          height: 2,
                          flex: 1,
                          background:
                            i < level && axisFraction(axis, level) > 0
                              ? axis.color
                              : "rgba(148, 163, 184, 0.4)",
                          borderRadius: 1,
                          marginBottom: 18,
                        }}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
            <span
              style={{
                fontSize: 10,
                fontFamily: F.mono,
                fontWeight: 700,
                color: axis.color,
                width: 96,
                textAlign: "right",
                flexShrink: 0,
              }}
            >
              {axisStepLabel(axis, level)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OverviewFieldsPanel({ ree }: { ree: ReeEditorViewModel }) {
  return <AllFieldsPanel ree={ree} />;
}

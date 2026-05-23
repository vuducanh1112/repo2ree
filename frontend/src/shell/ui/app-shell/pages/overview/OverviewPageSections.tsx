import React from "react";
import type { ArtifactStatus } from "../../../../../core/artifact/ArtifactStatus";
import type { Badges, Timestamps } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import { LEVELS } from "../../../../../core/review/levels";
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
  level,
  badges,
}: {
  ree: ReeEditorViewModel;
  level: number;
  badges: Badges;
}) {
  const levelMeta = LEVELS[Math.min(level, 7)];
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
  level: number;
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
  onSeal: () => void;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
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
        podSvgRef={refs.podSvgRef}
        level={props.level}
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
          onWorkspaceSourceStateChange={props.onWorkspaceSourceStateChange}
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
          onArtifactStatusChange={props.onArtifactStatusChange}
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
        <PodWidget level={props.level} svgRef={refs.podSvgRef} size={props.podSize} />

        <CenterSealStrip
          ree={props.ree}
          locked={props.locked}
          level={props.level}
          badges={props.badges}
          onSeal={props.onSeal}
          onPreviewReviewer={props.onPreviewReviewer}
          onDownloadRee={props.onDownloadRee}
          sealRef={refs.sealRef}
        />
      </div>

      <RightRailPanels
        ree={props.ree}
        badges={props.badges}
        timestamps={props.timestamps}
        level={props.level}
        onNavigate={props.onNavigate}
        onGoField={props.onGoField}
        swhRef={refs.swhRef}
        evaluateRef={refs.evaluateRef}
        archiveRef={refs.archiveRef}
        activationRef={refs.activationRef}
      />
    </div>
  );
}

export function OverviewLevelStrip({ level }: { level: number }) {
  return (
    <div style={{ ...lgStyles.overviewPanel, marginTop: 20, padding: "16px 20px" }}>
      <div
        style={{
          ...lgStyles.overviewLabel,
          marginBottom: 14,
        }}
      >
        Reproducibility Level
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        {LEVELS.map((levelConfig, i) => {
          const isReached = i <= level;
          const isCurrent = i === level;
          const isLast = i === LEVELS.length - 1;
          return (
            <React.Fragment key={levelConfig.n}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 5,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    width: isCurrent ? 14 : 9,
                    height: isCurrent ? 14 : 9,
                    borderRadius: "50%",
                    background: isReached ? levelConfig.color : "rgba(148, 163, 184, 0.4)",
                    border: isCurrent ? `2.5px solid ${levelConfig.color}` : "none",
                    boxShadow: isCurrent ? `0 0 0 4px ${levelConfig.color}22` : "none",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.4,
                    color: isReached ? levelConfig.ink : lgColors.textMuted,
                    background: isReached ? `${levelConfig.color}18` : "rgba(241, 245, 249, 0.7)",
                    border: `1px solid ${isReached ? `${levelConfig.color}40` : "rgba(148, 163, 184, 0.4)"}`,
                    borderRadius: 3,
                    padding: "0 5px",
                    lineHeight: "18px",
                    whiteSpace: "nowrap",
                  }}
                >
                  L{i}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: isCurrent ? 700 : 400,
                    color: isCurrent
                      ? lgColors.text
                      : isReached
                        ? lgColors.textMid
                        : lgColors.textMuted,
                    fontFamily: F.sans,
                    whiteSpace: "nowrap",
                  }}
                >
                  {levelConfig.label}
                </span>
              </div>
              {!isLast && (
                <div
                  style={{
                    height: 2,
                    flex: 1,
                    maxWidth: 28,
                    background: i < level ? levelConfig.color : "rgba(148, 163, 184, 0.4)",
                    borderRadius: 1,
                    flexShrink: 0,
                    marginBottom: 34,
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

export function OverviewFieldsPanel({ ree }: { ree: ReeEditorViewModel }) {
  return <AllFieldsPanel ree={ree} />;
}

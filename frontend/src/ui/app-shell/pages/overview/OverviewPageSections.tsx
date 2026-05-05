import React from "react";
import type { ReeEditorViewModel } from "../../../../application/ree-editor/reeEditorViewModel";
import type { AppShellPage } from "../../../../application/state/pages";
import type { ArtifactStatus } from "../../../../domain/artifact/ArtifactStatus";
import type { Badges, Timestamps } from "../../../../domain/ree/ReeTypes";
import { LEVELS } from "../../../../domain/review/levels";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../../../domain/workspace/WorkspaceSourceState";
import { fmtBytes } from "../../../shared/formatting";
import { C, F, S_SECTION_LABEL } from "../../../theme/theme";
import { AllFieldsPanel } from "./components/AllFieldsPanel";
import { CenterSealStrip } from "./components/CenterSealStrip";
import { HbomPanel } from "./components/HbomPanel";
import { MetadataPanel } from "./components/MetadataPanel";
import { RightRailPanels } from "./components/RightRailPanels";
import { RuntimePanel } from "./components/RuntimePanel";
import { SbomPanel } from "./components/SbomPanel";
import { SourcePanel } from "./components/SourcePanel";
import { PanelCableOverlay } from "./PanelCableOverlay";
import { PodWidget } from "./PodWidget";

export function OverviewHeader({ ree, level }: { ree: ReeEditorViewModel; level: number }) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  return (
    <div style={{ marginBottom: 20, display: "flex", alignItems: "baseline", gap: 14 }}>
      <div>
        <div style={{ ...S_SECTION_LABEL, fontSize: 10, fontWeight: 600, marginBottom: 4 }}>
          Reproducible Execution Environment
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 800,
            color: C.text,
            letterSpacing: 0.2,
            fontFamily: F.mono,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          {ree.name || "untitled-env"}
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 3,
              letterSpacing: 1.5,
              textTransform: "uppercase",
              background: `${levelMeta.color}16`,
              color: levelMeta.color,
              border: `1px solid ${levelMeta.color}40`,
            }}
          >
            {levelMeta.label}
          </span>
        </div>
      </div>
      <div style={{ flex: 1, height: 1, background: C.border, marginBottom: 2 }} />
      <div style={{ fontSize: 9, fontFamily: F.mono, color: C.textMuted, letterSpacing: 1 }}>
        {new Date().toISOString().slice(0, 10)}
      </div>
    </div>
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
    <div style={{ marginTop: 20, display: "flex", alignItems: "center" }}>
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
                  background: isReached ? levelConfig.color : C.border,
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
                  color: isReached ? levelConfig.ink : C.textMuted,
                  background: isReached ? `${levelConfig.color}18` : C.surfaceAlt,
                  border: `1px solid ${isReached ? `${levelConfig.color}40` : C.border}`,
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
                  color: isCurrent ? C.text : isReached ? C.textMid : C.textMuted,
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
                  background: i < level ? levelConfig.color : C.border,
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
  );
}

export function OverviewFieldsPanel({ ree }: { ree: ReeEditorViewModel }) {
  return <AllFieldsPanel ree={ree} />;
}

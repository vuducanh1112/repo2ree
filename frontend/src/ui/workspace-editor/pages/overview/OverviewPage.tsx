import React, { useRef } from "react";
import type { WorkspaceEditorPage } from "../../../../application/workspace-editor/WorkspaceEditorPages";
import type { Ree } from "../../../../domain/ree/ReeSpec";
import type { Badges, Timestamps } from "../../../../domain/ree/ReeTypes";
import { LEVELS } from "../../../../domain/review/levels";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { listTreeFiles } from "../../../../domain/workspace/fileTreeTraversal";
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

interface PageOverviewProps {
  ree: Ree;
  onReeChange: (ree: Ree) => void;
  level: number;
  onNavigate: (key: WorkspaceEditorPage) => void;
  badges?: Badges;
  timestamps?: Timestamps;
  onGoField: (key: string) => void;
  files?: FileTreeNode[];
  snapshotFiles?: FileTreeNode[];
  locked?: boolean;
  onSeal: () => void;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
}
export function PageOverview({
  ree,
  onReeChange,
  level,
  onNavigate,
  badges = {},
  timestamps = {},
  onGoField,
  files = [],
  snapshotFiles = [],
  locked = false,
  onSeal,
  onPreviewReviewer,
  onDownloadRee,
}: PageOverviewProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];

  // Cable overlay refs
  const cableContainerRef = useRef<HTMLDivElement>(null);
  const sourceRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const hbomRef = useRef<HTMLDivElement>(null);
  const podColumnRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);

  // Responsive pod size — track center column width via ResizeObserver
  const [podSize, setPodSize] = React.useState(480);
  React.useEffect(() => {
    const el = podColumnRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      // Clamp: min 260 so the pod stays readable, max 620 so it doesn't overwhelm
      setPodSize(Math.min(640, Math.max(260, w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const swhRef = useRef<HTMLDivElement>(null);
  const evaluateRef = useRef<HTMLDivElement>(null);
  const sbomRef = useRef<HTMLDivElement>(null);
  const sealRef = useRef<HTMLDivElement>(null);
  const archiveRef = useRef<HTMLDivElement>(null);
  const activationRef = useRef<HTMLDivElement>(null);

  // Compute source file stats
  const allFiles = listTreeFiles(snapshotFiles);
  const fileCount = allFiles.length;
  const totalBytes = allFiles.reduce(
    (totalSize, file) =>
      totalSize + (file.content ? new TextEncoder().encode(file.content).length : 0),
    0,
  );

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: 28,
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          marginBottom: 20,
          display: "flex",
          alignItems: "baseline",
          gap: 14,
        }}
      >
        <div>
          <div
            style={{
              ...S_SECTION_LABEL,
              fontSize: 10,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
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
                ...{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 3,
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                },
                background: `${levelMeta.color}16`,
                color: levelMeta.color,
                border: `1px solid ${levelMeta.color}40`,
              }}
            >
              {levelMeta.label}
            </span>
          </div>
        </div>
        <div
          style={{
            flex: 1,
            height: 1,
            background: C.border,
            marginBottom: 2,
          }}
        />
        <div
          style={{
            fontSize: 9,
            fontFamily: F.mono,
            color: C.textMuted,
            letterSpacing: 1,
          }}
        >
          {new Date().toISOString().slice(0, 10)}
        </div>
      </div>

      {/* ── Three columns ── */}
      <div
        ref={cableContainerRef}
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 18,
          position: "relative",
        }}
      >
        <PanelCableOverlay
          containerRef={cableContainerRef}
          sourceRef={sourceRef}
          runtimeRef={runtimeRef}
          metadataRef={leftPanelRef}
          hbomRef={hbomRef}
          swhRef={swhRef}
          evaluateRef={evaluateRef}
          sbomRef={sbomRef}
          sealRef={sealRef}
          archiveRef={archiveRef}
          activationRef={activationRef}
          podSvgRef={podSvgRef}
          level={level}
          badges={badges}
          ree={ree}
        />

        {/* Left — source + fields */}
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
            ree={ree}
            sourceRef={sourceRef}
            fileCount={fileCount}
            fileSummary={`${fileCount} file${fileCount !== 1 ? "s" : ""} · ${fmtBytes(totalBytes)}`}
            onGoField={onGoField}
            onNavigate={onNavigate}
            onReeChange={onReeChange}
          />

          <MetadataPanel
            ree={ree}
            onGoField={onGoField}
            onNavigate={onNavigate}
            metadataRef={leftPanelRef}
          />

          <HbomPanel ree={ree} hbomRef={hbomRef} onGoField={onGoField} onNavigate={onNavigate} />

          <RuntimePanel
            ree={ree}
            files={files}
            runtimeRef={runtimeRef}
            onGoField={onGoField}
            onNavigate={onNavigate}
            onReeChange={onReeChange}
          />

          <SbomPanel
            ree={ree}
            files={files}
            badges={badges}
            sbomRef={sbomRef}
            onNavigate={onNavigate}
          />
        </div>

        {/* Center — pod + artifact bar + status */}
        <div
          ref={podColumnRef}
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
          <PodWidget level={level} svgRef={podSvgRef} size={podSize} />

          <CenterSealStrip
            ree={ree}
            locked={locked}
            level={level}
            badges={badges}
            onSeal={onSeal}
            onPreviewReviewer={onPreviewReviewer}
            onDownloadRee={onDownloadRee}
            sealRef={sealRef}
          />
        </div>

        <RightRailPanels
          ree={ree}
          badges={badges}
          timestamps={timestamps}
          level={level}
          onNavigate={onNavigate}
          onGoField={onGoField}
          swhRef={swhRef}
          evaluateRef={evaluateRef}
          archiveRef={archiveRef}
          activationRef={activationRef}
        />
      </div>

      {/* ── Horizontal level strip ── */}
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

      <AllFieldsPanel ree={ree} />
    </div>
  );
}

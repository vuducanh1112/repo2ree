import { useMemo, useRef, useState } from "react";
import { standingMeta } from "../../../../core/evaluate/axes";
import type { EvaluationState } from "../../../../core/evaluate/EvaluationState";
import type { Badges, ReeFile } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { SourceRepoMetadata } from "../../../../core/workspace/WorkspaceTypes";
import { C, F } from "../../theme/theme";
import type { AppShellPage } from "../state/pages";
import { BenchConsole } from "./BenchConsole";
import { CableOverlaySvg } from "./CableOverlay";
import { CanvasControls } from "./CanvasControls";
import {
  CANVAS_NODES,
  EXPLODE_CENTER,
  EXPLODE_LAYERS,
  EXPLODE_ZOOM,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  lifecycleProgress,
  nodeProjection,
  nodeSummary,
} from "./canvasNodes";
import { ExplodeScaffold, ExplodeToggle, ProjectionPod } from "./ExplodeView";
import { FileTreeConsole } from "./FileTreeConsole";
import { LabBackdrop } from "./LabBackdrop";
import { NodeCard } from "./NodeCard";
import { useCableGeometry } from "./useCableGeometry";
import { type Transform, useCanvasViewport } from "./useCanvasViewport";

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  dimmed: boolean;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  reeFiles: ReeFile[];
  sourceRepo: SourceRepoMetadata | undefined;
  filesConsoleOpen: boolean;
  onFilesConsoleOpenChange: (open: boolean) => void;
}

export function CanvasHub({
  page,
  ree,
  evaluation,
  badges,
  provisioned,
  dimmed,
  onNavigate,
  reeFiles,
  sourceRepo,
  filesConsoleOpen,
  onFilesConsoleOpenChange,
}: CanvasHubProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const innerPodRef = useRef<SVGSVGElement>(null);
  const corePodRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});

  const {
    tf,
    animate,
    nodeOffsets,
    wasNodeDragged,
    isPanning,
    startPan,
    startNodeDrag,
    resetView,
    zoomBy,
    focusView,
  } = useCanvasViewport(stageRef);

  const [exploded, setExploded] = useState(false);
  // The pan/zoom the user had before decomposing, restored when they reassemble.
  const preExplodeTf = useRef<Transform | null>(null);

  // Pull the camera back and centre the spread when decomposing; on reassemble,
  // return to wherever the user was framed before, not a hard reset.
  const toggleExplode = () => {
    const next = !exploded;
    if (next) {
      preExplodeTf.current = tf;
      focusView({ x: -EXPLODE_CENTER * EXPLODE_ZOOM, y: 0, z: EXPLODE_ZOOM });
    } else {
      focusView(preExplodeTf.current ?? { x: 0, y: 0, z: 1 });
    }
    setExploded(next);
  };

  const projectionPods = useMemo(() => ({ inner: innerPodRef, core: corePodRef }), []);

  const geo = useCableGeometry({
    stageRef,
    podSvgRef,
    worldRef,
    nodeEls,
    ree,
    badges,
    tf,
    nodeOffsets,
    animate,
    exploded,
    projectionPods,
  });

  const { completed, total } = lifecycleProgress(ree, badges);
  const ready = completed >= total;
  const levelMeta = standingMeta(evaluation);

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: pannable canvas surface; nodes inside are buttons
    <div
      ref={stageRef}
      onMouseDown={startPan}
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        cursor: isPanning ? "grabbing" : "grab",
        opacity: dimmed ? 0.4 : 1,
        transition: "opacity 0.3s",
        boxShadow: "inset 0 0 220px rgba(30,58,138,0.10)",
        background: `
          radial-gradient(120% 75% at 50% -8%, #ffffff 0%, rgba(255,255,255,0) 58%),
          radial-gradient(58% 48% at 18% 22%, rgba(56,189,248,0.12) 0%, rgba(56,189,248,0) 70%),
          radial-gradient(54% 44% at 83% 16%, rgba(129,140,248,0.12) 0%, rgba(129,140,248,0) 72%),
          radial-gradient(75% 60% at 50% 118%, rgba(13,148,136,0.10) 0%, rgba(13,148,136,0) 72%),
          linear-gradient(${C.border}cc 1px, transparent 1px) 0 0 / 130px 130px,
          linear-gradient(90deg, ${C.border}cc 1px, transparent 1px) 0 0 / 130px 130px,
          linear-gradient(${C.border}55 1px, transparent 1px) 0 0 / 26px 26px,
          linear-gradient(90deg, ${C.border}55 1px, transparent 1px) 0 0 / 26px 26px,
          radial-gradient(circle at 50% 44%, #f6fafe 0%, ${C.bg} 72%)`,
      }}
    >
      <LabBackdrop />

      {geo && <CableOverlaySvg geo={geo} levelMeta={levelMeta} />}

      <div
        ref={worldRef}
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transformOrigin: "0 0",
          transform: `translate(${tf.x}px, ${tf.y}px) scale(${tf.z})`,
          transition: animate ? "transform 0.4s cubic-bezier(0.4,0,0.2,1)" : "none",
        }}
      >
        {/* cradle socket: the pod is seated in the bench, not floating */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 96,
            width: 320,
            height: 96,
            transform: "translate(-50%,-50%)",
            borderRadius: "50%",
            background:
              "radial-gradient(ellipse at center, rgba(100,116,139,0.14) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />
        {/* projection axis + per-column captions for the decomposed view */}
        <ExplodeScaffold exploded={exploded} />

        {/* the specimen, plus its shrinking projections to the right (real pod
            entities the inner/core cables anchor to) */}
        <ProjectionPod
          evaluation={evaluation}
          svgRef={podSvgRef}
          layer={EXPLODE_LAYERS[0]}
          exploded={exploded}
        />
        <ProjectionPod
          evaluation={evaluation}
          svgRef={innerPodRef}
          layer={EXPLODE_LAYERS[1]}
          exploded={exploded}
        />
        <ProjectionPod
          evaluation={evaluation}
          svgRef={corePodRef}
          layer={EXPLODE_LAYERS[2]}
          exploded={exploded}
        />

        <nav aria-label="Workspace pages">
          {CANVAS_NODES.map((node) => {
            const off = nodeOffsets[node.key] ?? { x: 0, y: 0 };
            return (
              <NodeCard
                key={node.key}
                node={node}
                offsetX={off.x}
                offsetY={off.y}
                setRef={(el) => {
                  nodeEls.current[node.key] = el;
                }}
                done={isNodeDone(node, ree, badges)}
                locked={isNodeLocked(node, provisioned)}
                active={isNodeActive(node, page)}
                rows={nodeSummary(node, ree, sourceRepo)}
                projection={nodeProjection(node, exploded)}
                onNavigate={onNavigate}
                onStartDrag={startNodeDrag}
                wasNodeDragged={wasNodeDragged}
              />
            );
          })}
        </nav>
      </div>

      <div
        style={{
          position: "absolute",
          top: 16,
          left: "50%",
          transform: "translateX(-50%)",
          fontFamily: F.mono,
          fontSize: 11.5,
          color: ready ? C.done : C.textMid,
          background: "rgba(255,255,255,0.8)",
          border: `1px solid ${C.border}`,
          borderRadius: 99,
          padding: "6px 14px",
          backdropFilter: "blur(4px)",
        }}
      >
        {ready ? (
          <b style={{ color: C.done }}>● archive-ready</b>
        ) : (
          <>
            <b style={{ color: C.text }}>{completed}</b>
            <span style={{ color: C.textMuted }}> / {total} stages connected</span>
          </>
        )}
      </div>

      <FileTreeConsole
        reeFiles={reeFiles}
        open={filesConsoleOpen}
        onOpenChange={onFilesConsoleOpenChange}
      />

      <BenchConsole provisioned={provisioned} reeName={ree.name} />

      <ExplodeToggle exploded={exploded} onToggle={toggleExplode} />

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onReset={resetView}
      />
    </div>
  );
}

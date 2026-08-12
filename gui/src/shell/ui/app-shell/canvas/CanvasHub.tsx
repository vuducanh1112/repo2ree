import type { AppShellPage } from "@core/app-shell/pages";
import { PAGE } from "@core/app-shell/pages";
import {
  CANVAS_NODES,
  EXPLODE_BASE_POD,
  EXPLODE_CENTER,
  EXPLODE_LAYERS,
  EXPLODE_ZOOM,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  nodeProjection,
  nodeSummary,
} from "@core/canvas/canvasNodes";
import { satellitePositions } from "@core/canvas/experimentRing";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { Badges, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useMemo, useRef, useState } from "react";
import { cssVars } from "../../theme/styleVars";
import { BenchConsole } from "./BenchConsole";
import { CableOverlaySvg } from "./CableOverlay";
import { CanvasControls } from "./CanvasControls";
import styles from "./CanvasHub.module.css";
import { CoreExperiments, experimentCableTargets } from "./CoreExperiments";
import { ExplodeScaffold, ExplodeToggle, ProjectionPod } from "./ExplodeView";
import { FileTreeConsole } from "./FileTreeConsole";
import { InnerShellButton } from "./InnerShellButton";
import { LabBackdrop } from "./LabBackdrop";
import { NodeCard } from "./NodeCard";
import { ReceiptsConsole } from "./ReceiptsConsole";
import { ReviewConsole } from "./ReviewConsole";
import { useCableGeometry } from "./useCableGeometry";
import { type Transform, useCanvasViewport } from "./useCanvasViewport";
import { useExperimentCables } from "./useExperimentCables";

// The core column (rightmost decomposed shell) hosts the experiment satellites.
const CORE_LAYER = EXPLODE_LAYERS[EXPLODE_LAYERS.length - 1];
const CORE_CENTER = { x: CORE_LAYER.cx, y: 0 };
const CORE_POD_DIAMETER = EXPLODE_BASE_POD * CORE_LAYER.scale;
// The inner column (middle shell) is the runtime — its pod opens the Runtime page.
const INNER_LAYER = EXPLODE_LAYERS[1];
const INNER_CENTER = { x: INNER_LAYER.cx, y: 0 };
const INNER_POD_DIAMETER = EXPLODE_BASE_POD * INNER_LAYER.scale;
// Satellites render full-size: the exploded world is already scaled to
// EXPLODE_ZOOM, so any extra shrink here makes the panels unreadable. The ring
// radius (experimentRing) keeps them clear of the core pod.
const CORE_SAT_SCALE = 1;

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  dimmed: boolean;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  onAddExperiment: () => void;
  /** Core pod → the experiment catalog overview (clears any deep-link). */
  onOpenExperimentsOverview: () => void;
  /** Open one experiment's editor (satellite click in the decompose view). */
  onOpenExperiment: (index: number) => void;
  /** Inner-shell pod → the runtime environment page. */
  onOpenRuntime: () => void;
  reeFiles: ReeFile[];
  sourceRepo: SourceRepoMetadata | undefined;
  /** Node keys whose recorded run result is stale (see sealConsistency). */
  staleNodeKeys?: ReadonlySet<string>;
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
  onAddExperiment,
  onOpenExperimentsOverview,
  onOpenExperiment,
  onOpenRuntime,
  reeFiles,
  sourceRepo,
  staleNodeKeys,
  filesConsoleOpen,
  onFilesConsoleOpenChange,
}: CanvasHubProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const innerPodRef = useRef<SVGSVGElement>(null);
  const corePodRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const satEls = useRef<Record<string, HTMLElement | null>>({});

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
  // Hover over the core pod (the experiment-catalog affordance) makes it shine.
  const [coreHovered, setCoreHovered] = useState(false);
  // Same for the inner pod, which opens the runtime environment page.
  const [innerHovered, setInnerHovered] = useState(false);
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

  // Decomposed, the core column becomes the experiment space: one satellite per
  // experiment cabled to the core pod, plus an add-ghost slot.
  const experiments = ree.experiments ?? [];
  // Once sealed the REE is frozen, so the ring drops its add-ghost slot.
  const withAddSlot = !ree.sealedAt;
  const satellitePos = useMemo(
    () => satellitePositions(experiments.length, withAddSlot),
    [experiments.length, withAddSlot],
  );
  const expTargets = useMemo(
    () => (exploded ? experimentCableTargets(experiments, withAddSlot) : []),
    [exploded, experiments, withAddSlot],
  );
  const expGeo = useExperimentCables({
    stageRef,
    coreSvgRef: corePodRef,
    worldRef,
    satEls,
    targets: expTargets,
    tf,
    nodeOffsets,
    animate,
  });

  const levelMeta = {
    color: "var(--chrome-accent)",
    bg: "var(--chrome-surface-alt)",
    label: "REE evidence",
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: pannable canvas surface; nodes inside are buttons
    <div
      ref={stageRef}
      onMouseDown={startPan}
      className={styles.stage}
      data-panning={isPanning || undefined}
      data-dimmed={dimmed || undefined}
    >
      <LabBackdrop />

      {geo && <CableOverlaySvg geo={geo} levelMeta={levelMeta} />}

      {exploded && expGeo && <CableOverlaySvg geo={expGeo} levelMeta={levelMeta} />}

      <div
        ref={worldRef}
        className={styles.world}
        data-animate={animate || undefined}
        style={cssVars({
          "--world-x": `${tf.x}px`,
          "--world-y": `${tf.y}px`,
          "--world-z": tf.z,
        })}
      >
        {/* cradle socket: the pod is seated in the bench, not floating */}
        <div aria-hidden className={styles.cradle} />
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
          glow={exploded && innerHovered}
        />
        <ProjectionPod
          evaluation={evaluation}
          svgRef={corePodRef}
          layer={EXPLODE_LAYERS[2]}
          exploded={exploded}
          glow={exploded && coreHovered}
        />

        {/* The inner pod opens the build runtime page. Rendered before the nav so
            the inner-shell node cards keep painting (and clicking) on top of it. */}
        {exploded && (
          <InnerShellButton
            center={INNER_CENTER}
            podDiameter={INNER_POD_DIAMETER}
            wasNodeDragged={wasNodeDragged}
            onHoverChange={setInnerHovered}
            onOpenRuntime={onOpenRuntime}
          />
        )}

        <nav aria-label="Workspace pages">
          {CANVAS_NODES.map((node) => {
            // Decomposed, the core column is taken over by the experiment
            // satellites, so the lone Experiments node steps aside.
            if (exploded && node.key === PAGE.EXPERIMENTS) return null;
            // Decomposed, the inner shell itself is the build-runtime entry
            // point (it's clickable here), so the Build node steps aside.
            if (exploded && node.key === PAGE.BUILD) return null;
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
                stale={staleNodeKeys?.has(node.key) ?? false}
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

        {exploded && (
          <CoreExperiments
            experiments={experiments}
            locked={!withAddSlot}
            center={CORE_CENTER}
            podDiameter={CORE_POD_DIAMETER}
            positions={satellitePos}
            scale={CORE_SAT_SCALE}
            satEls={satEls}
            nodeOffsets={nodeOffsets}
            onStartDrag={startNodeDrag}
            wasNodeDragged={wasNodeDragged}
            onCoreHoverChange={setCoreHovered}
            onOpenOverview={onOpenExperimentsOverview}
            onOpenExperiment={onOpenExperiment}
            onAddExperiment={onAddExperiment}
          />
        )}
      </div>

      <FileTreeConsole
        reeFiles={reeFiles}
        open={filesConsoleOpen}
        onOpenChange={onFilesConsoleOpenChange}
      />

      <ReceiptsConsole provisioned={provisioned} />

      <BenchConsole provisioned={provisioned} reeName={ree.name} />

      <ReviewConsole experiments={experiments} />

      <ExplodeToggle exploded={exploded} onToggle={toggleExplode} />

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onReset={resetView}
      />
    </div>
  );
}

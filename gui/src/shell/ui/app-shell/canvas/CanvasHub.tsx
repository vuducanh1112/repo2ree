import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { canvasActivity } from "@core/canvas/canvasActivity";
import { offsetOf, placedNodes } from "@core/canvas/canvasLayout";
import {
  CANVAS_NODES,
  canvasWorldBounds,
  FLOOR_TILT_DEGREES,
  isNodeActive,
  isNodeDone,
  nodeOverview,
  RING,
  SCENE_DEPTH,
} from "@core/canvas/canvasNodes";
import { latestCrossCheckSummary } from "@core/evaluate/crossCheckRun";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { memo, useCallback, useMemo, useRef, useState } from "react";
import { cssVars } from "../../theme/styleVars";
import { BenchConsole } from "./BenchConsole";
import { CableOverlaySvg } from "./CableOverlay";
import { CanvasControls } from "./CanvasControls";
import styles from "./CanvasHub.module.css";
import { FileTreeConsole } from "./FileTreeConsole";
import { LabBackdrop } from "./LabBackdrop";
import { NodeCard } from "./NodeCard";
import { ReceiptsConsole } from "./ReceiptsConsole";
import { SpecimenPod } from "./SpecimenPod";
import { useCableGeometry } from "./useCableGeometry";
import { useCanvasLayout } from "./useCanvasLayout";
import { useCanvasViewport } from "./useCanvasViewport";

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  /** The page the authoring graph says to do next; its panel is flagged. */
  nextPage?: AppShellPage;
  /** Canvas node keys whose authoring prerequisites are not yet met. */
  blockedNodeKeys?: ReadonlySet<string>;
  /** Sealing runs on the client, so it has no entry in the run listing. */
  sealRunning?: boolean;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  workspaceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  sourceRepo: SourceRepoMetadata | undefined;
  authorReceipts: ReceiptView[];
  /** Node keys whose recorded run result is stale (see sealConsistency). */
  staleNodeKeys?: ReadonlySet<string>;
  filesConsoleOpen: boolean;
  onFilesConsoleOpenChange: (open: boolean) => void;
  receiptsConsoleOpen: boolean;
  onReceiptsConsoleOpenChange: (open: boolean) => void;
  benchConsoleOpen: boolean;
  onBenchConsoleOpenChange: (open: boolean) => void;
}

export const CanvasHub = memo(function CanvasHub({
  page,
  ree,
  evaluation,
  badges,
  provisioned,
  nextPage,
  blockedNodeKeys,
  sealRunning = false,
  onNavigate,
  workspaceFiles,
  reeFiles,
  sourceRepo,
  authorReceipts,
  staleNodeKeys,
  filesConsoleOpen,
  onFilesConsoleOpenChange,
  receiptsConsoleOpen,
  onReceiptsConsoleOpenChange,
  benchConsoleOpen,
  onBenchConsoleOpenChange,
}: CanvasHubProps) {
  const { data: scriptTemplates } = useScriptTemplates();
  // Read live work from the run listing rather than from what this tab started,
  // so a step an agent (or another tab) is running lights up here too.
  const { data: runs } = useReeRunsQuery();
  const activity = useMemo(
    () => canvasActivity(runs ?? [], sealRunning ? [PAGE.SEAL] : []),
    [runs, sealRunning],
  );
  // The arrangement is saved per REE, under the same scope the data hooks use.
  const { layout, moveNode, resetLayout, isDefault } = useCanvasLayout(useReeId());
  // A panel is only ever dragged one at a time, and this flips once at each end
  // of the gesture rather than on every pointer move — it exists to keep the
  // cable measure loop running while a panel is moving, not to place anything.
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const onDraggingChange = useCallback((key: string, dragging: boolean) => {
    setDraggingKey(dragging ? key : null);
  }, []);
  // Bounds follow the arrangement: `fitView` has to frame the bench as the user
  // has it, or dragging a panel outward would put it beyond the fitted view.
  const nodes = useMemo(() => placedNodes(layout, CANVAS_NODES), [layout]);
  const assembledBounds = useMemo(() => canvasWorldBounds(nodes), [nodes]);
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const nodePortEls = useRef<Record<string, HTMLSpanElement | null>>({});

  const { tf, animate, isPanning, startPan, fitView, zoomBy } = useCanvasViewport(
    stageRef,
    assembledBounds,
  );

  const onResetLayout = useCallback(() => {
    resetLayout();
    fitView();
  }, [resetLayout, fitView]);

  const geo = useCableGeometry({
    stageRef,
    podSvgRef,
    worldRef,
    nodeEls,
    nodePortEls,
    ree,
    badges,
    tf,
    // Cables are measured from the DOM, so they follow a moved panel for free —
    // but only if something keeps re-measuring while it moves.
    animate: animate || draggingKey !== null,
  });

  const levelMeta = {
    color: "var(--chrome-accent)",
    bg: "var(--chrome-surface-alt)",
    label: "REE evidence",
  };

  return (
    <div
      ref={stageRef}
      onPointerDown={startPan}
      className={styles.stage}
      data-panning={isPanning || undefined}
    >
      <LabBackdrop />

      {geo && <CableOverlaySvg geo={geo} levelMeta={levelMeta} runningKeys={activity.nodeKeys} />}

      <div
        ref={worldRef}
        className={styles.camera}
        data-animate={animate || undefined}
        style={cssVars({
          "--world-x": `${tf.x}px`,
          "--world-y": `${tf.y}px`,
          "--world-z": tf.z,
          // The tilt and the scene depth come from core so the geometry the
          // layout is computed against and the geometry the browser draws are
          // the same two numbers.
          "--floor-tilt": `${FLOOR_TILT_DEGREES}deg`,
          "--panel-counter-tilt": `${-FLOOR_TILT_DEGREES}deg`,
          "--scene-depth": `${SCENE_DEPTH}px`,
          // The floor rings are drawn from the same ellipse the nodes stand on,
          // so the deck markings describe the layout instead of decorating it.
          "--ring-rx": `${RING.rx}px`,
          "--ring-ry": `${RING.ry}px`,
        })}
      >
        <div className={styles.perspective}>
          <div className={styles.floor}>
            <div aria-hidden className={styles.floorGrid} />
            <div aria-hidden className={styles.zoneRing} data-zone="outer" />
            <div aria-hidden className={styles.zoneRing} data-zone="inner" />
            <div aria-hidden className={styles.zoneRing} data-zone="core" />
            {/* cradle socket: the pod is seated in the bench, not floating */}
            <div aria-hidden className={styles.cradle} />

            <SpecimenPod evaluation={evaluation} svgRef={podSvgRef} activity={activity} />

            <nav aria-label="Workspace pages">
              {nodes.map((node) => {
                const overview = nodeOverview(node, ree, sourceRepo, {
                  workspaceFiles: [...workspaceFiles, ...reeFiles],
                  receipts: authorReceipts,
                  buildScriptPath: scriptTemplates?.build.path,
                  crossCheck: latestCrossCheckSummary(runs ?? []),
                });
                return (
                  <NodeCard
                    key={node.key}
                    node={node}
                    setRef={(el) => {
                      nodeEls.current[node.key] = el;
                    }}
                    setPortRef={(el) => {
                      nodePortEls.current[node.key] = el;
                    }}
                    done={isNodeDone(node, ree, badges)}
                    stale={staleNodeKeys?.has(node.key) ?? false}
                    active={isNodeActive(node, page)}
                    running={activity.nodeKeys.has(node.key)}
                    next={node.key === nextPage}
                    blocked={blockedNodeKeys?.has(node.key)}
                    overview={overview}
                    onNavigate={onNavigate}
                    offset={offsetOf(layout, node.key)}
                    zoom={tf.z}
                    onMove={moveNode}
                    onDraggingChange={onDraggingChange}
                  />
                );
              })}
            </nav>
          </div>
        </div>
      </div>

      <FileTreeConsole
        workspaceFiles={workspaceFiles}
        reeFiles={reeFiles}
        open={filesConsoleOpen}
        onOpenChange={onFilesConsoleOpenChange}
        externallyTriggered
      />

      <ReceiptsConsole
        provisioned={provisioned}
        receipts={authorReceipts}
        open={receiptsConsoleOpen}
        onOpenChange={onReceiptsConsoleOpenChange}
        externallyTriggered
      />

      <BenchConsole
        provisioned={provisioned}
        reeName={ree.spec.name}
        open={benchConsoleOpen}
        onOpenChange={onBenchConsoleOpenChange}
        externallyTriggered
      />

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onFit={fitView}
        onResetLayout={onResetLayout}
        layoutIsDefault={isDefault}
      />
    </div>
  );
});

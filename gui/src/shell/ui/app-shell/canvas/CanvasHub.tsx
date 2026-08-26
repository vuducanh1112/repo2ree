import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { canvasActivity } from "@core/canvas/canvasActivity";
import {
  CANVAS_NODES,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  nodeOverview,
} from "@core/canvas/canvasNodes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { memo, useMemo, useRef } from "react";
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
import { useCanvasViewport } from "./useCanvasViewport";

// Includes the 2.5D floor ring, pod, and lifted cards. These are intentionally
// conservative unprojected bounds; the fixed floor tilt compresses their
// screen-space height further.
const ASSEMBLED_BOUNDS = { left: -930, top: -620, width: 1960, height: 1240 } as const;

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  /** The page the authoring graph says to do next; its panel is flagged. */
  nextPage?: AppShellPage;
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
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const nodePortEls = useRef<Record<string, HTMLSpanElement | null>>({});

  const { tf, animate, isPanning, startPan, fitView, zoomBy } = useCanvasViewport(
    stageRef,
    ASSEMBLED_BOUNDS,
  );

  const geo = useCableGeometry({
    stageRef,
    podSvgRef,
    worldRef,
    nodeEls,
    nodePortEls,
    ree,
    badges,
    tf,
    animate,
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
          "--floor-tilt": "54deg",
          "--panel-counter-tilt": "-54deg",
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
              {CANVAS_NODES.map((node) => {
                const overview = nodeOverview(node, ree, sourceRepo, {
                  workspaceFiles: [...workspaceFiles, ...reeFiles],
                  receipts: authorReceipts,
                  buildScriptPath: scriptTemplates?.build.path,
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
                    done={isNodeDone(node, ree, badges) || !!overview.receipt}
                    stale={staleNodeKeys?.has(node.key) ?? false}
                    locked={isNodeLocked(node, provisioned)}
                    active={isNodeActive(node, page)}
                    running={activity.nodeKeys.has(node.key)}
                    next={node.key === nextPage}
                    overview={overview}
                    onNavigate={onNavigate}
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
      />
    </div>
  );
});

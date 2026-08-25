import type { AppShellPage } from "@core/app-shell/pages";
import {
  CANVAS_NODES,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  nodeSummary,
} from "@core/canvas/canvasNodes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { memo, useEffect, useRef } from "react";
import { cssVars } from "../../theme/styleVars";
import { AuthoringConsole } from "./AuthoringConsole";
import { BenchConsole } from "./BenchConsole";
import { CableOverlaySvg } from "./CableOverlay";
import { CanvasControls } from "./CanvasControls";
import styles from "./CanvasHub.module.css";
import { FileTreeConsole } from "./FileTreeConsole";
import { LabBackdrop } from "./LabBackdrop";
import { NodeCard } from "./NodeCard";
import { ReceiptsConsole } from "./ReceiptsConsole";
import { ReviewConsole } from "./ReviewConsole";
import { SpecimenPod } from "./SpecimenPod";
import { useCableGeometry } from "./useCableGeometry";
import { useCanvasViewport } from "./useCanvasViewport";

// Includes the 2.5D floor ring, pod, and lifted cards. These are intentionally
// conservative unprojected bounds; the fixed floor tilt compresses their
// screen-space height further.
const ASSEMBLED_BOUNDS = { left: -930, top: -620, width: 1860, height: 1240 } as const;

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  dimmed: boolean;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  workspaceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  sourceRepo: SourceRepoMetadata | undefined;
  authorReceipts: ReceiptView[];
  /** Node keys whose recorded run result is stale (see sealConsistency). */
  staleNodeKeys?: ReadonlySet<string>;
  filesConsoleOpen: boolean;
  onFilesConsoleOpenChange: (open: boolean) => void;
}

export const CanvasHub = memo(function CanvasHub({
  page,
  ree,
  evaluation,
  badges,
  provisioned,
  dimmed,
  onNavigate,
  workspaceFiles,
  reeFiles,
  sourceRepo,
  authorReceipts,
  staleNodeKeys,
  filesConsoleOpen,
  onFilesConsoleOpenChange,
}: CanvasHubProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const nodePortEls = useRef<Record<string, HTMLSpanElement | null>>({});

  const { tf, animate, isPanning, startPan, fitView, zoomBy } = useCanvasViewport(
    stageRef,
    ASSEMBLED_BOUNDS,
  );

  // A focused step page behaves as a modal over the constellation. `inert`
  // removes this background canvas from both keyboard navigation and the
  // accessibility tree while the dock is open; the visual dimming alone does
  // not communicate that interaction boundary to assistive technology.
  useEffect(() => {
    stageRef.current?.toggleAttribute("inert", dimmed);
  }, [dimmed]);

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

  const experiments = ree.spec.experiments ?? [];

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
      data-dimmed={dimmed || undefined}
    >
      <LabBackdrop />

      {geo && <CableOverlaySvg geo={geo} levelMeta={levelMeta} />}

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

            <SpecimenPod evaluation={evaluation} svgRef={podSvgRef} />

            <nav aria-label="Workspace pages">
              {CANVAS_NODES.map((node) => {
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
                    locked={isNodeLocked(node, provisioned)}
                    active={isNodeActive(node, page)}
                    rows={nodeSummary(node, ree, sourceRepo)}
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
      />

      <ReceiptsConsole provisioned={provisioned} receipts={authorReceipts} />

      <BenchConsole provisioned={provisioned} reeName={ree.spec.name} />

      <ReviewConsole experiments={experiments} />

      <AuthoringConsole page={page} ree={ree} badges={badges} onNavigate={onNavigate} />

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onFit={fitView}
      />
    </div>
  );
});

import type { OpenPageWindow } from "@core/app-shell/openPages";
import type { AppShellPage } from "@core/app-shell/pages";
import type { Point } from "@core/canvas/cableGeometry";
import {
  activeNode,
  CANVAS_NODES,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  nodeSummary,
} from "@core/canvas/canvasNodes";
import {
  cascadeClear,
  DEFAULT_WINDOW_SIZE,
  placeNodeWindow,
  resizeWindowBy,
  type WindowSize,
} from "@core/canvas/nodeWindowPlacement";
import { toCameraLocal, toStagePoint } from "@core/canvas/viewportMath";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { memo, type ReactNode, useEffect, useRef } from "react";
import { cssVars } from "../../theme/styleVars";
import { BenchConsole } from "./BenchConsole";
import { CableOverlaySvg } from "./CableOverlay";
import { CanvasControls } from "./CanvasControls";
import styles from "./CanvasHub.module.css";
import { CanvasPageWindow } from "./CanvasPageWindow";
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
const ASSEMBLED_BOUNDS = { left: -930, top: -620, width: 1860, height: 1240 } as const;

interface CanvasHubProps {
  page: AppShellPage;
  /** Every page with a window on this canvas, oldest first, and where it stands. */
  openPages: readonly OpenPageWindow[];
  /**
   * The window body for one open page. Callers must keep the returned element
   * referentially stable per page: a pan re-renders this component every frame,
   * and a stable element is what stops React reconciling the page beneath it.
   */
  renderPage: (page: AppShellPage) => ReactNode;
  onClosePage: (page: AppShellPage) => void;
  /** Records where a window stands, in camera-local space. */
  onPositionPage: (page: AppShellPage, position: Point) => void;
  /** Records one window's independent screen-space size. */
  onSizePage: (page: AppShellPage, size: WindowSize) => void;
  /** Longer window title for pages whose node label is a compact one. */
  pageTitle: (page: AppShellPage) => string | undefined;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
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
  openPages,
  renderPage,
  onClosePage,
  onPositionPage,
  onSizePage,
  pageTitle,
  ree,
  evaluation,
  badges,
  provisioned,
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
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const nodePortEls = useRef<Record<string, HTMLSpanElement | null>>({});

  const { tf, animate, isPanning, startPan, fitView, zoomBy, bringIntoView } = useCanvasViewport(
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

  const stageBox = { width: geo?.w ?? 0, height: geo?.h ?? 0 };

  // A window's stored point is where it stands on the canvas; this is where
  // that currently lands on screen. Nothing is clamped: pan far enough and a
  // window leaves the stage, like anything else standing on the canvas.
  const windowPositions = openPages.map((open) =>
    open.position ? toStagePoint(open.position, stageBox, tf) : null,
  );

  // Now that a window can be panned off the stage, focusing one has to be able
  // to reach it — otherwise a page is open and unreachable. Only a window that
  // is actually out of sight moves the camera; focusing a visible one must not
  // yank the view off whatever the user was looking at.
  const focused = openPages.find((open) => open.page === page);
  const broughtIntoView = useRef<AppShellPage | null>(null);
  useEffect(() => {
    const standing = focused?.position;
    const size = focused?.size ?? DEFAULT_WINDOW_SIZE;
    if (broughtIntoView.current === page || !standing || stageBox.width === 0) return;
    broughtIntoView.current = page;
    const spot = toStagePoint(standing, stageBox, tf);
    const offStage =
      spot.x < 0 ||
      spot.y < 0 ||
      spot.x + size.width > stageBox.width ||
      spot.y + size.height > stageBox.height;
    if (!offStage) return;
    // Centre the window, not its corner: a window is most of the stage wide.
    bringIntoView({
      x: standing.x + size.width / 2 / tf.z,
      y: standing.y + size.height / 2 / tf.z,
    });
  });

  // A window is placed once, on the first measure after it opens, and then
  // remembers where it was put. Deriving the position every frame instead made
  // a window slide along the stage edge rather than leave it, and flip to the
  // other side of its node the moment that node crossed the stage's midline.
  useEffect(() => {
    if (!geo) return;
    const taken = windowPositions.filter((spot): spot is Point => spot !== null);
    for (const [index, open] of openPages.entries()) {
      if (windowPositions[index]) continue;
      const anchor = geo.nodeRects[open.page];
      if (!anchor) continue;
      const size = open.size ?? DEFAULT_WINDOW_SIZE;
      const spot = cascadeClear(placeNodeWindow(anchor, stageBox, size), taken, stageBox, size);
      onPositionPage(open.page, toCameraLocal(spot, stageBox, tf));
      return;
    }
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

      {/* Pages stand in this untransformed layer, beside the 3D floor rather
       * than on it, so their text and controls never take the floor's tilt. */}
      {openPages.map((open, depth) => {
        const spot = windowPositions[depth];
        // Nothing to draw until the first measure has given it a place.
        if (!spot || !open.position) return null;
        return (
          <CanvasPageWindow
            key={open.page}
            node={activeNode(open.page)}
            title={pageTitle(open.page)}
            subtitle={open.page === page ? "Authoring" : "Open"}
            position={spot}
            size={open.size}
            depth={depth}
            focused={open.page === page}
            onFocus={() => onNavigate(open.page)}
            onClose={() => onClosePage(open.page)}
            // Screen-space drag, stored on the canvas: a drag of N pixels moves
            // the window N/z across the canvas, so it keeps pace with the
            // pointer at any zoom.
            onMove={(delta) =>
              onPositionPage(open.page, {
                x: (open.position?.x ?? 0) + delta.x / tf.z,
                y: (open.position?.y ?? 0) + delta.y / tf.z,
              })
            }
            onResize={(delta) =>
              onSizePage(
                open.page,
                resizeWindowBy(open.size ?? DEFAULT_WINDOW_SIZE, delta, stageBox),
              )
            }
          >
            {renderPage(open.page)}
          </CanvasPageWindow>
        );
      })}

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onFit={fitView}
      />
    </div>
  );
});

import type { Point, Rect } from "@core/canvas/cableGeometry";

// Where a page's window sits relative to the node it belongs to. The hooks
// measure the node, this decides the placement, and the window's own module
// draws it — the same split `cableScene` and `cableGeometry` already use.

export interface WindowSize {
  width: number;
  height: number;
}

interface StageBox {
  width: number;
  height: number;
}

export const DEFAULT_WINDOW_SIZE: WindowSize = { width: 700, height: 540 };
export const MIN_WINDOW_SIZE: WindowSize = { width: 420, height: 300 };

/** Breathing room between a window and its node, and between a window and the stage edge. */
const NODE_GAP = 20;
const STAGE_MARGIN = 12;

function clamp(value: number, low: number, high: number): number {
  // A window wider than the stage has no valid position; pinning it to the low
  // edge at least keeps its title bar and close button reachable.
  return high < low ? low : Math.min(high, Math.max(low, value));
}

/** Resize in screen space while keeping the page usable and its handle reachable. */
export function resizeWindowBy(size: WindowSize, delta: Point, stage: StageBox): WindowSize {
  const maxWidth = Math.max(MIN_WINDOW_SIZE.width, stage.width - STAGE_MARGIN * 2);
  const maxHeight = Math.max(MIN_WINDOW_SIZE.height, stage.height - STAGE_MARGIN * 2);
  return {
    width: clamp(size.width + delta.x, MIN_WINDOW_SIZE.width, maxWidth),
    height: clamp(size.height + delta.y, MIN_WINDOW_SIZE.height, maxHeight),
  };
}

/**
 * Place a page window beside the node it opens from.
 *
 * The nodes ring a pod at the stage's centre, so a window opens on its node's
 * outward side — away from the pod — and falls back to the inward side only
 * when it would not fit outward. It is then clamped into the stage, because a
 * node near an edge would otherwise push its window halfway out of view.
 *
 * Some overlap is expected rather than avoided: the ring spans most of the
 * stage and a window is a large fraction of its width, so at anything but the
 * closest zoom there is no placement that clears both the pod and the cards.
 * The rule picks the least-bad side; the window's own stacking does the rest.
 */
export function placeNodeWindow(anchor: Rect, stage: StageBox, size: WindowSize): Point {
  const nodeCenterX = (anchor.left + anchor.right) / 2;
  const outwardIsLeft = nodeCenterX < stage.width / 2;

  const leftward = anchor.left - NODE_GAP - size.width;
  const rightward = anchor.right + NODE_GAP;
  const fits = (x: number) => x >= STAGE_MARGIN && x + size.width <= stage.width - STAGE_MARGIN;

  const outward = outwardIsLeft ? leftward : rightward;
  const inward = outwardIsLeft ? rightward : leftward;
  const left = fits(outward) || !fits(inward) ? outward : inward;
  // Vertically the window centres on its node rather than sitting beside it:
  // the ring is wider than it is tall, so vertical room is the scarce one.
  const top = anchor.top + (anchor.bottom - anchor.top) / 2 - size.height / 2;

  return {
    x: clamp(left, STAGE_MARGIN, stage.width - size.width - STAGE_MARGIN),
    y: clamp(top, STAGE_MARGIN, stage.height - size.height - STAGE_MARGIN),
  };
}

// How far a window has to clear the one under it for both title bars — and so
// both windows' names and close buttons — to stay visible.
const CASCADE_X = 34;
const CASCADE_Y = 44;
const MAX_CASCADE = 6;

function collides(a: Point, b: Point): boolean {
  return Math.abs(a.x - b.x) < CASCADE_X && Math.abs(a.y - b.y) < CASCADE_Y;
}

/**
 * Nudge a freshly placed window clear of the ones already standing.
 *
 * Placing a window against its own node alone is not enough: the ring clusters
 * declarations to the left and evidence to the right, so two windows opened
 * from neighbouring nodes resolve to nearly the same spot and the second hides
 * the first entirely. A window that would land on another cascades down and
 * across instead — far enough that every title bar stays readable, which is
 * what makes a stack of windows navigable rather than just a pile.
 *
 * Only about two windows of this size fit a stage without overlapping at all,
 * so a legible overlap is the goal, not no overlap.
 */
export function cascadeClear(
  base: Point,
  occupied: readonly Point[],
  stage: StageBox,
  size: WindowSize,
): Point {
  let spot = base;
  for (let step = 1; occupied.some((other) => collides(spot, other)); step++) {
    if (step > MAX_CASCADE) break;
    spot = {
      x: clamp(base.x + CASCADE_X * step, STAGE_MARGIN, stage.width - size.width - STAGE_MARGIN),
      y: clamp(base.y + CASCADE_Y * step, STAGE_MARGIN, stage.height - size.height - STAGE_MARGIN),
    };
  }
  return spot;
}

import type { CanvasNode } from "./canvasNodes";
import { CANVAS_NODES, floorPointFromScreen, screenPointFromFloor } from "./canvasNodes";

/**
 * Where a panel has been moved to, relative to the spot the ring puts it.
 *
 * Offsets rather than absolute positions on purpose: the default layout is a
 * rule (`angle` plus `RING`), and it will be retuned again. Storing the
 * difference means a retune moves everyone's arranged canvas with it instead of
 * stranding it against coordinates that no longer mean anything.
 */
export interface NodeOffset {
  dx: number;
  dy: number;
}

export type CanvasLayout = Readonly<Record<string, NodeOffset>>;

export const DEFAULT_LAYOUT: CanvasLayout = {};

const NO_OFFSET: NodeOffset = { dx: 0, dy: 0 };

/**
 * Bumped whenever the default ring changes shape. Offsets are measured from
 * that default, so a stored layout from before a retune describes an
 * arrangement its owner never made — and the failure is silent and permanent
 * for anyone who ever dragged a panel. Discarding on mismatch costs one
 * rearrangement; keeping it costs a canvas that is quietly wrong forever.
 */
export const LAYOUT_VERSION = 1;

interface StoredLayout {
  version: number;
  offsets: Record<string, NodeOffset>;
}

export function offsetOf(layout: CanvasLayout, key: string): NodeOffset {
  return layout[key] ?? NO_OFFSET;
}

/** The node as it currently stands, with any offset the user has given it. */
export function placedNode(node: CanvasNode, layout: CanvasLayout): CanvasNode {
  const offset = offsetOf(layout, node.key);
  if (offset.dx === 0 && offset.dy === 0) return node;
  return { ...node, x: node.x + offset.dx, y: node.y + offset.dy };
}

export function placedNodes(
  layout: CanvasLayout,
  nodes: readonly CanvasNode[] = CANVAS_NODES,
): CanvasNode[] {
  return nodes.map((node) => placedNode(node, layout));
}

/** An offset of zero is an absence, so a layout back at its default is empty. */
export function withNodeMoved(layout: CanvasLayout, key: string, offset: NodeOffset): CanvasLayout {
  const next = { ...layout };
  if (offset.dx === 0 && offset.dy === 0) delete next[key];
  else next[key] = offset;
  return next;
}

export function withNodeReset(layout: CanvasLayout, key: string): CanvasLayout {
  return withNodeMoved(layout, key, NO_OFFSET);
}

export function isDefaultLayout(layout: CanvasLayout): boolean {
  return Object.keys(layout).length === 0;
}

/**
 * Move a panel by a distance measured on screen rather than on the floor.
 *
 * A drag is a screen gesture, and the floor is tilted and in perspective, so
 * the same number of pixels means different amounts of bench depending on where
 * the panel already stands. Projecting out, adding the delta, and inverting
 * back is what makes a panel track the pointer instead of sliding away from it.
 */
export function nodeOffsetAfterDrag(
  node: CanvasNode,
  offset: NodeOffset,
  screenDelta: { dx: number; dy: number },
): NodeOffset {
  const from = { x: node.x + offset.dx, y: node.y + offset.dy };
  const projected = screenPointFromFloor(from);
  const moved = floorPointFromScreen({
    x: projected.x + screenDelta.dx,
    y: projected.y + screenDelta.dy,
  });
  return { dx: moved.x - node.x, dy: moved.y - node.y };
}

export function serializeLayout(layout: CanvasLayout): string {
  return JSON.stringify({ version: LAYOUT_VERSION, offsets: layout } satisfies StoredLayout);
}

/**
 * Anything unrecognised reads as "no saved layout". A stored arrangement is a
 * convenience, never data worth failing a canvas over, so every bad shape —
 * unparseable, wrong version, a non-numeric offset written by a future build —
 * takes the same quiet path back to the default.
 */
export function parseStoredLayout(raw: string | null | undefined): CanvasLayout {
  if (!raw) return DEFAULT_LAYOUT;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return DEFAULT_LAYOUT;
  }
  if (typeof parsed !== "object" || parsed === null) return DEFAULT_LAYOUT;
  const stored = parsed as Partial<StoredLayout>;
  if (stored.version !== LAYOUT_VERSION) return DEFAULT_LAYOUT;
  if (typeof stored.offsets !== "object" || stored.offsets === null) return DEFAULT_LAYOUT;

  const known = new Set(CANVAS_NODES.map((node) => node.key as string));
  const offsets: Record<string, NodeOffset> = {};
  for (const [key, value] of Object.entries(stored.offsets)) {
    // A key for a node that no longer exists is dropped rather than carried.
    if (!known.has(key)) continue;
    const offset = value as Partial<NodeOffset> | null;
    if (!offset || !Number.isFinite(offset.dx) || !Number.isFinite(offset.dy)) continue;
    if (offset.dx === 0 && offset.dy === 0) continue;
    offsets[key] = { dx: offset.dx as number, dy: offset.dy as number };
  }
  return offsets;
}

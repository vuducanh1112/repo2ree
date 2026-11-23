import type { CanvasNode } from "./canvasNodes";
import { CANVAS_NODES, floorPointFromScreen, screenPointFromFloor } from "./canvasNodes";

export interface NodeOffset {
  dx: number;
  dy: number;
}

export type CanvasLayout = Readonly<Record<string, NodeOffset>>;

export const DEFAULT_LAYOUT: CanvasLayout = {};

const NO_OFFSET: NodeOffset = { dx: 0, dy: 0 };

export const LAYOUT_VERSION = 1;

interface StoredLayout {
  version: number;
  offsets: Record<string, NodeOffset>;
}

export function offsetOf(layout: CanvasLayout, key: string): NodeOffset {
  return layout[key] ?? NO_OFFSET;
}

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
    if (!known.has(key)) continue;
    const offset = value as Partial<NodeOffset> | null;
    if (!offset || !Number.isFinite(offset.dx) || !Number.isFinite(offset.dy)) continue;
    if (offset.dx === 0 && offset.dy === 0) continue;
    offsets[key] = { dx: offset.dx as number, dy: offset.dy as number };
  }
  return offsets;
}

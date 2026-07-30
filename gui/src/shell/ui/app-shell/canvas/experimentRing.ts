// Layout math for the experiment satellites in the decompose view's core column.
// Each experiment is a panel cabled to the core pod, ringed evenly around it. The
// ring radius grows with the population so cards never crowd the pod or each
// other, and the trailing "add" ghost gets its own slot — spawning a new
// experiment reads as lighting up that slot. Positions are centred on (0,0); the
// caller translates them onto the core pod's world location.

interface SatellitePos {
  x: number;
  y: number;
}

const BASE_RADIUS = 300;
const COMFORTABLE_SLOTS = 5;
const RADIUS_PER_EXTRA_SLOT = 18;
// First slot sits due north; the rest fan clockwise from there.
const START_ANGLE = -Math.PI / 2;

function ringRadius(slotCount: number): number {
  return BASE_RADIUS + Math.max(0, slotCount - COMFORTABLE_SLOTS) * RADIUS_PER_EXTRA_SLOT;
}

// Even angular placement for `count` experiment satellites, plus one trailing
// slot for the add-ghost when `withAddSlot` is set. The add-ghost is always the
// last entry, so callers index it at `count`.
export function satellitePositions(count: number, withAddSlot: boolean): SatellitePos[] {
  const slots = count + (withAddSlot ? 1 : 0);
  if (slots === 0) return [];
  const r = ringRadius(slots);
  const positions: SatellitePos[] = [];
  for (let i = 0; i < slots; i += 1) {
    const angle = START_ANGLE + (i / slots) * Math.PI * 2;
    positions.push({ x: Math.cos(angle) * r, y: Math.sin(angle) * r });
  }
  return positions;
}

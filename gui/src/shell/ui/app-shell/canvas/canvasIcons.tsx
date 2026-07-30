import type { CanvasIconKey } from "@core/canvas/canvasNodes";
import { Ic } from "../../shared/components/Icon";

// Key -> glyph, the shell half of the indirection that keeps CANVAS_NODES in the
// functional core. Mirrors stepIcons.tsx, which does the same for ReeStepIconKey.
const CANVAS_ICONS: Record<CanvasIconKey, (size?: number) => JSX.Element> = {
  archive: Ic.archive,
  chip: Ic.chip,
  cpu: Ic.cpu,
  globe: Ic.globe,
  grid: Ic.grid,
  lock: Ic.lock,
  package: Ic.package,
  shield: Ic.shield,
  star: Ic.star,
  terminal: Ic.terminal,
};

export function canvasIcon(iconKey: CanvasIconKey) {
  return CANVAS_ICONS[iconKey];
}

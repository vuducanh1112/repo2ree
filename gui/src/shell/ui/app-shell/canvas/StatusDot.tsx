import { C } from "../../theme/theme";

const STALE_AMBER = "#f59e0b";

/** 7px indicator dot used on canvas HUD consoles and node cards.
 *
 * ``stale`` ambers a lit dot: the step has a result, but its recorded inputs
 * no longer match the workspace (see sealConsistency).
 */
export function StatusDot({ on, stale = false }: { on: boolean; stale?: boolean }) {
  const color = stale ? STALE_AMBER : C.done;
  return (
    <span
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        flexShrink: 0,
        background: on ? color : C.borderMid,
        boxShadow: on ? `0 0 7px ${color}88` : "none",
      }}
    />
  );
}

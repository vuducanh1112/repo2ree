import styles from "./StatusDot.module.css";

/** 7px indicator dot used on canvas HUD consoles and node cards.
 *
 * ``stale`` ambers a lit dot: the step has a result, but its recorded inputs
 * no longer match the workspace (see sealConsistency).
 */
export function StatusDot({ on, stale = false }: { on: boolean; stale?: boolean }) {
  const state = !on ? "idle" : stale ? "stale" : "ready";
  return <span className={styles.dot} data-state={state} />;
}

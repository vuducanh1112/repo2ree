import styles from "./StatusDot.module.css";

export function StatusDot({ on, stale = false }: { on: boolean; stale?: boolean }) {
  const state = !on ? "idle" : stale ? "stale" : "ready";
  return <span className={styles.dot} data-state={state} />;
}

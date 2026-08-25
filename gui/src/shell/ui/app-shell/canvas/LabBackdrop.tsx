import styles from "./LabBackdrop.module.css";

/**
 * Decorative, non-interactive lab atmosphere behind the pod: drifting ambient
 * light pools, an overhead glass light bar, and a slow scanning sheen over the
 * projected bench. Pure CSS, pointer-events disabled.
 */
export function LabBackdrop() {
  return (
    <div aria-hidden className={styles.backdrop}>
      <div className={styles.pool} data-side="left" />
      <div className={styles.pool} data-side="right" />
      <div className={styles.bar} />
      <div className={styles.beam} />
      <div className={styles.scan} />
    </div>
  );
}

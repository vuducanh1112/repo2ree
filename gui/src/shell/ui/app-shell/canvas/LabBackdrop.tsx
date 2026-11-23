import styles from "./LabBackdrop.module.css";

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

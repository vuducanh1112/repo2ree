import styles from "./RepoAnalysisPage.module.css";

export function CardHeader({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className={styles.cardHeader}>
      <div className={styles.cardLabel}>{label}</div>
      {hint && <span className={styles.cardHint}>{hint}</span>}
    </div>
  );
}

import styles from "./RepoAnalysisPage.module.css";

/** Shared label/hint header row used by the repo-analysis result cards. */
export function CardHeader({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className={styles.cardHeader}>
      <div className={styles.cardLabel}>{label}</div>
      {hint && <span className={styles.cardHint}>{hint}</span>}
    </div>
  );
}

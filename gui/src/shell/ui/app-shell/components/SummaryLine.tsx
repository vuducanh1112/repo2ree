import type React from "react";
import styles from "./SummaryLine.module.css";

export function SummaryLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className={styles.line}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  );
}

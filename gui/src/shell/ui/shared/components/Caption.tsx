import type { ReactNode } from "react";
import styles from "./Caption.module.css";

interface CaptionProps {
  title: ReactNode;
  hint?: ReactNode;
}

export function Caption({ title, hint }: CaptionProps) {
  return (
    <div>
      <div className={styles.title}>{title}</div>
      {hint && <div className={styles.hint}>{hint}</div>}
    </div>
  );
}

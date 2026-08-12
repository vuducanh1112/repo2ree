import type { ReactNode } from "react";
import styles from "./Caption.module.css";

interface CaptionProps {
  title: ReactNode;
  /** The explanatory line under the title. */
  hint?: ReactNode;
}

/**
 * A card's title and the sentence explaining it. Not a `Field` label — this
 * names a region rather than a control, which is why it is a plain heading pair
 * and carries no `htmlFor`.
 */
export function Caption({ title, hint }: CaptionProps) {
  return (
    <div>
      <div className={styles.title}>{title}</div>
      {hint && <div className={styles.hint}>{hint}</div>}
    </div>
  );
}

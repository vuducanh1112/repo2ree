import type { ReactNode } from "react";
import styles from "./Notice.module.css";

type NoticeTone = "info" | "success" | "danger";

interface NoticeProps {
  tone?: NoticeTone;
  /** A heading line above the body. Stacks the notice when present. */
  title?: ReactNode;
  icon?: ReactNode;
  children?: ReactNode;
}

/**
 * The one banner. A `danger` notice is announced as an alert so a missing
 * prerequisite reaches a screen reader when it appears, rather than only when
 * the user happens to tab through the region.
 */
export function Notice({ tone = "info", title, icon, children }: NoticeProps) {
  return (
    <div
      className={styles.notice}
      data-tone={tone}
      data-layout={title ? "stacked" : undefined}
      role={tone === "danger" ? "alert" : undefined}
    >
      {title && (
        <span className={styles.title}>
          {icon && (
            <span aria-hidden className={styles.icon}>
              {icon}
            </span>
          )}
          {title}
        </span>
      )}
      {!title && icon && (
        <span aria-hidden className={styles.icon}>
          {icon}
        </span>
      )}
      {children}
    </div>
  );
}

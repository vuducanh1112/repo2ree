import type { ReactNode } from "react";
import styles from "./Notice.module.css";

type NoticeTone = "info" | "success" | "danger";

interface NoticeProps {
  tone?: NoticeTone;
  title?: ReactNode;
  icon?: ReactNode;
  children?: ReactNode;
}

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

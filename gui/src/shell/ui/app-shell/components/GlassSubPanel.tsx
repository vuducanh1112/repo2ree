import type React from "react";
import styles from "./GlassPage.module.css";

export function GlassSubPanel({ children }: { children: React.ReactNode }) {
  return <div className={styles.subPanel}>{children}</div>;
}

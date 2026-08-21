import type { ReactNode } from "react";
import styles from "./pageContainers.module.css";

export function ContentSection({ children }: { children: ReactNode }) {
  return <div className={styles.contentSection}>{children}</div>;
}

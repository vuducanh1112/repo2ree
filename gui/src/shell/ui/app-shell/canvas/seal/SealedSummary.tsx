import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import styles from "../SealContent.module.css";

/** What the seal produced: the content identity the REE is now addressed by,
 *  and when it was frozen. Shown in place of the bundle choices, which the
 *  seal has already consumed. */
export function SealedSummary({ ree }: { ree: ReeEditorViewModel }) {
  const sealDate = new Date(ree.artifact.sealedAt ?? new Date().toISOString()).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={styles.sealedMeta}>
      <div className={styles.metaRow}>
        <span className={styles.metaKey}>hash</span>
        <span className={styles.metaHash}>{ree.artifact.sealHash || "—"}</span>
      </div>
      <div className={styles.metaRow}>
        <span className={styles.metaKey}>sealed</span>
        <span className={styles.metaDate}>{sealDate}</span>
      </div>
    </div>
  );
}

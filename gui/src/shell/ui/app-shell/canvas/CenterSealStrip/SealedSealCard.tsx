import type { SealCableItem } from "@core/canvas/sealCableScene";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { Ic } from "@shell/ui/shared/components/Icon";
import { cssVars } from "@shell/ui/theme/styleVars";
import type React from "react";
import styles from "./CenterSealStrip.module.css";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealedSealCardProps {
  ree: ReeEditorViewModel;
  sealRef: React.RefObject<HTMLDivElement>;
  cableItems: SealCableItem[];
  currentLevelMeta: LevelMeta;
}

export function SealedSealCard({
  ree,
  sealRef,
  cableItems,
  currentLevelMeta,
}: SealedSealCardProps) {
  const sealDate = new Date(ree.artifact.sealedAt ?? new Date().toISOString()).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      ref={sealRef}
      className={styles.sealed}
      style={cssVars({ "--seal-tint": currentLevelMeta.color })}
    >
      <div className={styles.sealedBar}>
        <span aria-hidden className={styles.sealedIcon}>
          {Ic.lock(13)}
        </span>
        <span className={styles.sealedTitle}>REE SEALED</span>
        <span className={styles.sealedLevel}>{currentLevelMeta.label}</span>
      </div>
      <div className={styles.sealedBody}>
        <div className={styles.metaRow}>
          <span className={styles.metaKey}>hash</span>
          <span className={styles.metaHash}>{ree.artifact.sealHash || "—"}</span>
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaKey}>sealed</span>
          <span className={styles.metaDate}>{sealDate}</span>
        </div>
        <div className={styles.sealedTrack}>
          {cableItems.map((item) => (
            <div
              key={item.label}
              title={item.label}
              className={styles.sealedSegment}
              data-live={item.live || undefined}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

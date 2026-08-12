import styles from "./CenterSealStrip.module.css";

interface SealConfirmWarningProps {
  missing: { key: string; label: string }[];
}

function WarningGroup({
  headline,
  items,
}: {
  headline: string;
  items: { key: string; text: string }[];
}) {
  return (
    <div>
      <div className={styles.warningHeadline}>{headline}</div>
      <div className={styles.warningItems}>
        {items.map((item) => (
          <div key={item.key} className={styles.warningItem}>
            <div aria-hidden className={styles.warningDot} />
            <span className={styles.warningText}>{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SealConfirmWarning({ missing }: SealConfirmWarningProps) {
  return (
    <div className={styles.warning}>
      <div className={styles.warningRow}>
        <span aria-hidden className={styles.warningGlyph}>
          ⚠️
        </span>
        <div className={styles.warningGroups}>
          {missing.length > 0 && (
            <WarningGroup
              headline={`${missing.length} panel${missing.length !== 1 ? "s" : ""} not connected`}
              items={missing.map((item) => ({
                key: item.key,
                text: `${item.label} — not completed`,
              }))}
            />
          )}
        </div>
      </div>
    </div>
  );
}

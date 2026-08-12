import styles from "./CenterSealStrip.module.css";

interface SealConfirmCopyProps {
  allLive: boolean;
  totalCables: number;
  currentLabel: string;
}

export function SealConfirmCopy({ allLive, totalCables, currentLabel }: SealConfirmCopyProps) {
  return (
    <div className={styles.copy}>
      <div>
        {allLive ? (
          <>
            All <strong>{totalCables}</strong> panels are connected. The REE will be frozen at{" "}
            <strong>{currentLabel}</strong> and become read-only.
          </>
        ) : (
          <>
            Sealing now will freeze the REE at <strong>{currentLabel}</strong> with incomplete data.
            You can still seal, but the missing panels will not be part of the record.
          </>
        )}
      </div>
    </div>
  );
}

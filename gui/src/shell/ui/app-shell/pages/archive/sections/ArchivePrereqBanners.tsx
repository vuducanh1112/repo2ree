import { Ic } from "@shell/ui/shared/components/Icon";
import styles from "../ArchivePage.module.css";

interface ArchivePrereqBannersProps {
  capstoneReady: boolean;
  buildDone: boolean;
  sbomDone: boolean;
  activationDone: boolean;
  isSealed: boolean;
}

function PrereqChip({ label }: { label: string }) {
  return <span className={styles.prereq}>✗ {label}</span>;
}

export function ArchivePrereqBanners({
  capstoneReady,
  buildDone,
  sbomDone,
  activationDone,
  isSealed,
}: ArchivePrereqBannersProps) {
  return (
    <>
      {!capstoneReady && (
        <div className={styles.advisory} data-tone="warn">
          <span aria-hidden className={styles.advisoryIcon}>
            {Ic.info()}
          </span>
          <div className={styles.advisoryBody}>
            <div className={styles.advisoryTitle}>Complete earlier steps before depositing</div>
            <div className={styles.advisoryCopy}>
              Archiving before building and validating risks depositing an environment that can't be
              reproduced. Complete these steps first:
            </div>
            <div className={styles.prereqs}>
              {!buildDone && <PrereqChip label="Build Runtime not run" />}
              {!sbomDone && <PrereqChip label="SBOM not generated" />}
              {!activationDone && <PrereqChip label="Activation test not run" />}
            </div>
          </div>
        </div>
      )}

      {!isSealed && (
        <div className={styles.advisory} data-tone="info">
          <span aria-hidden className={styles.advisoryIcon}>
            {Ic.info()}
          </span>
          <div className={styles.advisoryBody}>
            Deposit can proceed before sealing, but the final Seal step is still required before
            your REE is considered complete.
          </div>
        </div>
      )}
    </>
  );
}

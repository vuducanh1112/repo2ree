import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { SummaryLine } from "../../components/SummaryLine";
import styles from "./SourceAcquisitionPage.module.css";

interface Step3Props {
  step3Ready: boolean;
  acquisitionNarrative: string;
  sourceMeta: SourceRepoMetadata | undefined;
}

export function SourceStep3Section(props: Step3Props) {
  const { sourceMeta } = props;
  return (
    <section aria-label="Workspace Snapshot" className={styles.snapshotSection}>
      <div className={styles.snapshotLabel}>Workspace Snapshot</div>

      {props.step3Ready && sourceMeta ? (
        <div className={styles.snapshotBody}>
          <div className={styles.narrative}>{props.acquisitionNarrative}</div>

          <div className={styles.facts}>
            <SummaryLine label="Name" value={sourceMeta.name} />
            <SummaryLine label="Origin" value={sourceMeta.origin || "—"} />
            <SummaryLine label="Type" value={sourceMeta.sourceType || "—"} />
            <SummaryLine label="Size" value={sourceMeta.sizeLabel ?? "—"} />
            <SummaryLine
              label="SWHID"
              value={
                sourceMeta.swhid ? (
                  <span className={styles.swhid}>{sourceMeta.swhid}</span>
                ) : (
                  "Not computed yet"
                )
              }
            />
          </div>
        </div>
      ) : (
        <div className={styles.hint}>
          Complete the Source Snapshot step above to configure snapshot behavior.
        </div>
      )}
    </section>
  );
}

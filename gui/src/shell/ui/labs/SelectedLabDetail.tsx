import type { Lab } from "@core/lab/Lab";
import { connectedDurationMs, formatDuration } from "@core/lab/Lab";
import { dockerModeCopy } from "./labPresentation";
import styles from "./SelectedLabDetail.module.css";

interface SelectedLabDetailProps {
  lab: Lab | null;
  nowMs: number;
}

/**
 * What the specimen is about to be committed to. The grid is where you choose;
 * this is where you confirm — it carries the operator facts a cell has no room
 * for, so picking and reading them don't compete for the same space.
 */
export function SelectedLabDetail({ lab, nowMs }: SelectedLabDetailProps) {
  if (!lab) {
    return (
      <div className={styles.detail} data-empty>
        <div className={styles.kind}>Specimen pod · unassigned</div>
        <div className={styles.name}>No lab chosen</div>
        <div className={styles.what}>Pick a lab from the grid to assign this REE to it.</div>
      </div>
    );
  }

  const mode = dockerModeCopy(lab.dockerMode);
  const facts: [string, string][] = [
    ["ISOLATION", mode.readout],
    ["WORKBENCH", lab.id],
    ["UPTIME", formatDuration(connectedDurationMs(lab, nowMs))],
    ["VERSION", lab.version || "—"],
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.kind}>Specimen pod · assigned</div>
      <div className={styles.name}>{lab.hostname || lab.id}</div>
      <div className={styles.what}>{mode.line}</div>
      <dl className={styles.facts}>
        {facts.map(([key, value]) => (
          <div key={key} className={styles.row}>
            <dt className={styles.key}>{key}</dt>
            <dd className={styles.value}>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

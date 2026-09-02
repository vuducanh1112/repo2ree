import type { Lab } from "@core/lab/Lab";
import { dockerModeCopy } from "./labPresentation";
import styles from "./SelectedLabDetail.module.css";

interface SelectedLabDetailProps {
  lab: Lab | null;
}

/**
 * What the specimen is about to be committed to. The grid is where you choose;
 * this is where you confirm — it carries the operator facts a cell has no room
 * for, so picking and reading them don't compete for the same space.
 */
export function SelectedLabDetail({ lab }: SelectedLabDetailProps) {
  if (!lab) {
    return (
      <div className={styles.detail} data-empty>
        <div className={styles.kind}>Specimen pod · unassigned</div>
        <div className={styles.name}>No lab chosen</div>
        <div className={styles.what}>Pick a lab from the grid to assign this REE to it.</div>
      </div>
    );
  }

  const profile = lab.profiles[0];
  const mode = dockerModeCopy(profile?.substrate ?? "");
  const facts: [string, string][] = [
    ["SUBSTRATE", mode.readout],
    ["LOCATION", lab.id],
    ["LIFECYCLE", lab.lifecycleMode === "provider_managed" ? "on demand" : "pre-provisioned"],
    ["PROFILES", String(lab.profiles.length)],
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.kind}>Specimen pod · assigned</div>
      <div className={styles.name}>{lab.label}</div>
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

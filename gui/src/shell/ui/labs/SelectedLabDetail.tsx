import { revisionLabel } from "@core/build/buildInfo";
import { describeMachine, type Lab } from "@core/lab/Lab";
import styles from "./SelectedLabDetail.module.css";

interface SelectedLabDetailProps {
  lab: Lab | null;
}

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

  const facts: [string, string][] = [
    ["LOCATION", lab.id],
    ["MACHINE", describeMachine(lab.machine)],
    ["WORKBENCH REV", revisionLabel(lab.build?.revision)],
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.kind}>Specimen pod · assigned</div>
      <div className={styles.name}>{lab.label}</div>
      <div className={styles.what}>{lab.description || "Keeps this REE for its whole life."}</div>
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

import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { dockerModeCopy } from "./agentPresentation";
import styles from "./SelectedLabDetail.module.css";

interface SelectedLabDetailProps {
  agent: Agent | null;
  nowMs: number;
}

/**
 * What the specimen is about to be committed to. The grid is where you choose;
 * this is where you confirm — it carries the operator facts a cell has no room
 * for, so picking and reading them don't compete for the same space.
 */
export function SelectedLabDetail({ agent, nowMs }: SelectedLabDetailProps) {
  if (!agent) {
    return (
      <div className={styles.detail} data-empty>
        <div className={styles.kind}>Specimen pod · unassigned</div>
        <div className={styles.name}>No lab chosen</div>
        <div className={styles.what}>Pick a lab from the grid to assign this REE to it.</div>
      </div>
    );
  }

  const mode = dockerModeCopy(agent.dockerMode);
  const facts: [string, string][] = [
    ["ISOLATION", mode.readout],
    ["AGENT", agent.id],
    ["UPTIME", formatDuration(connectedDurationMs(agent, nowMs))],
    ["VERSION", agent.version || "—"],
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.kind}>Specimen pod · assigned</div>
      <div className={styles.name}>{agent.hostname || agent.id}</div>
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

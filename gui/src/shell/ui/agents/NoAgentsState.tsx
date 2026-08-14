import { Ic } from "../shared/components/Icon";
import styles from "./NoAgentsState.module.css";

interface NoAgentsStateProps {
  description: string;
  standalone?: boolean;
}

/** The shared recovery instruction when the control plane has no runners. */
export function NoAgentsState({ description, standalone = false }: NoAgentsStateProps) {
  return (
    <div className={styles.empty} data-standalone={standalone || undefined}>
      <div aria-hidden className={styles.icon}>
        {Ic.cpu(24)}
      </div>
      <div className={styles.title}>No agents connected</div>
      <div className={styles.hint}>
        {description}
        <br />
        <code>WORKBENCH_API_WS_URL=ws://…/agent/connect python -m repo2ree_agent</code>
      </div>
    </div>
  );
}

import { Ic } from "../shared/components/Icon";
import styles from "./NoLabsState.module.css";

interface NoLabsStateProps {
  description: string;
  standalone?: boolean;
}

/** The shared recovery instruction when the control plane has no runners. */
export function NoLabsState({ description, standalone = false }: NoLabsStateProps) {
  return (
    <div className={styles.empty} data-standalone={standalone || undefined}>
      <div aria-hidden className={styles.icon}>
        {Ic.cpu(24)}
      </div>
      <div className={styles.title}>No labs connected</div>
      <div className={styles.hint}>
        {description}
        <br />
        <code>WORKBENCH_API_WS_URL=ws://…/lab/connect python -m repo2ree_workbench</code>
      </div>
    </div>
  );
}

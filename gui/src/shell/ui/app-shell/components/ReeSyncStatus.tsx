import type { ReeIntentSyncState } from "@shell/state/ree-editor/workspace-sync/useReeIntentSync";
import { Ic } from "../../shared/components/Icon";
import styles from "./ReeSyncStatus.module.css";

export function ReeSyncStatus({
  state,
  onRetry,
}: {
  state: ReeIntentSyncState;
  onRetry: () => void;
}) {
  if (state.phase === "error") {
    return (
      <button
        type="button"
        className={styles.status}
        data-phase="error"
        title={state.error.message}
        onClick={onRetry}
      >
        <span aria-hidden>{Ic.refresh(12)}</span>
        Save failed · Retry
      </button>
    );
  }

  return (
    <div className={styles.status} data-phase={state.phase} role="status" aria-live="polite">
      {state.phase === "saving" && <span aria-hidden>{Ic.loader(12)}</span>}
      {state.phase === "clean" ? "Saved" : state.phase === "saving" ? "Saving…" : "Unsaved"}
    </div>
  );
}

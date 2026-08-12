import type { SourceUploadCommit } from "@core/ree/ReeTypes";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import styles from "./SourceRuntime.module.css";

interface SourceUploadPendingProps {
  pending: SourceUploadCommit;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SourceUploadPending({ pending, onConfirm, onCancel }: SourceUploadPendingProps) {
  return (
    <div className={styles.pending}>
      <div className={styles.pendingRow}>
        <span aria-hidden className={styles.pendingIcon}>
          {Ic.archive()}
        </span>
        <span className={styles.pendingName}>{pending.archiveName}</span>
        <Button size="tiny" icon={Ic.check(11)} onClick={onConfirm}>
          Add to workspace
        </Button>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Discard pending upload"
          className={styles.dismiss}
        >
          {Ic.x(13)}
        </button>
      </div>
      <div className={styles.pendingNote}>
        {Ic.info(10)} Setting a new source will reset all downstream results.
      </div>
    </div>
  );
}

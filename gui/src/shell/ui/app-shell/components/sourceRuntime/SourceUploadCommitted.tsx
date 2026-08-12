import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import styles from "./SourceRuntime.module.css";

interface SourceUploadCommittedProps {
  committedName: string;
  inputDisabled: boolean;
  onReplace: () => void;
}

export function SourceUploadCommitted({
  committedName,
  inputDisabled,
  onReplace,
}: SourceUploadCommittedProps) {
  return (
    <div className={styles.committed}>
      <span aria-hidden className={styles.committedIcon}>
        {Ic.archive()}
      </span>
      <span className={styles.committedName}>{committedName}</span>
      {!inputDisabled && (
        <Button size="tiny" icon={Ic.upload(11)} onClick={onReplace}>
          Replace
        </Button>
      )}
    </div>
  );
}

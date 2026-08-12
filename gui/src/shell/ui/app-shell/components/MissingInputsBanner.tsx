import type { ReeStepRequirement } from "@core/ree-steps/stepTypes";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Notice } from "@shell/ui/shared/components/Notice";
import styles from "./MissingInputsBanner.module.css";

interface MissingInputsBannerProps {
  missing: ReeStepRequirement[];
  onGoFields?: () => void;
  /** Label for the jump-back button (when onGoFields is set). */
  goLabel?: string;
}

export function MissingInputsBanner({
  missing,
  onGoFields,
  goLabel = "Jump to required field",
}: MissingInputsBannerProps) {
  if (missing.length === 0) return null;
  return (
    <Notice tone="danger" icon={Ic.info(13)} title="Required inputs missing">
      <div className={styles.fields}>
        {missing.map((item) => (
          <span key={item.field} className={styles.field}>
            {item.label}
          </span>
        ))}
      </div>
      {onGoFields && (
        <div className={styles.action}>
          <Button variant="danger" size="small" onClick={onGoFields}>
            {goLabel}
          </Button>
        </div>
      )}
    </Notice>
  );
}

import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import styles from "./SourceRuntime.module.css";

interface SourceUrlFieldProps {
  locked: boolean;
  /** Live URL value, owned by the parent so a single Download button can act on it. */
  value: string;
  /** Previously committed origin, used to warn that a change resets downstream results. */
  priorValue?: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
}

const URL_PATTERN = /^https?:\/\/[^\s]+$/i;

export function isLikelySourceUrl(value: string): boolean {
  return URL_PATTERN.test(value.trim());
}

// Plain controlled input — no separate "check reachable" step. Reachability is
// validated as part of the single Download action in the parent, so typing a URL
// and pressing Download is the whole flow.
export function SourceUrlField({
  locked,
  value,
  priorValue,
  onChange,
  onFocus,
}: SourceUrlFieldProps) {
  const trimmed = value.trim();
  const valid = isLikelySourceUrl(value);
  const prior = (priorValue || "").trim();
  const changesPrior = !!prior && trimmed !== prior;

  return (
    <div className={styles.field}>
      <div className={styles.urlBox}>
        <div aria-hidden className={styles.urlIcon}>
          {Ic.link()}
        </div>
        <Input
          aria-label="Origin URL"
          adorned
          disabled={locked}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={onFocus}
          placeholder="https://github.com/org/repo"
          aria-invalid={trimmed !== "" && !valid}
        />
      </div>

      {changesPrior && (
        <div className={styles.status} data-tone="warning">
          {Ic.info(10)} Setting a new source will reset all downstream results.
        </div>
      )}

      {trimmed && !valid && (
        <div className={styles.status} data-tone="caution">
          {Ic.info(10)} Enter a full http(s) URL.
        </div>
      )}

      {valid && !changesPrior && (
        <div className={styles.status} data-tone="ok">
          {Ic.check(10)}
          <span className={styles.statusValue}>{trimmed}</span>
        </div>
      )}
    </div>
  );
}

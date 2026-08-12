import type { ReactNode } from "react";
import styles from "./SegmentedControl.module.css";

interface Segment<K extends string> {
  key: K;
  label: ReactNode;
  /** Rendered before the label, `aria-hidden`. */
  icon?: ReactNode;
  disabled?: boolean;
}

interface SegmentedControlProps<K extends string> {
  /** Names the group for assistive tech — "Acquisition method", "Archive". */
  label: string;
  segments: ReadonlyArray<Segment<K>>;
  value: K;
  onChange: (next: K) => void;
  /** Every segment shares the row equally, rather than sizing to its label. */
  stretch?: boolean;
  disabled?: boolean;
}

/**
 * Pick one of a few. A focused primitive rather than a `Button` variant,
 * because selection here is a different thing from pressing: the group is a
 * `tablist`-shaped choice, each option reports `aria-pressed`, and the selected
 * one is not "a button in a different colour" but the current state of a
 * setting.
 */
export function SegmentedControl<K extends string>({
  label,
  segments,
  value,
  onChange,
  stretch = false,
  disabled = false,
}: SegmentedControlProps<K>) {
  return (
    <fieldset className={styles.group} aria-label={label} data-stretch={stretch || undefined}>
      {segments.map((segment) => (
        <button
          key={segment.key}
          type="button"
          className={styles.segment}
          aria-pressed={segment.key === value}
          disabled={disabled || segment.disabled}
          onClick={() => onChange(segment.key)}
        >
          {segment.icon && (
            <span aria-hidden className={styles.icon}>
              {segment.icon}
            </span>
          )}
          {segment.label}
        </button>
      ))}
    </fieldset>
  );
}

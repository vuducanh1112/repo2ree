import type { ReactNode } from "react";
import styles from "./SegmentedControl.module.css";

interface Segment<K extends string> {
  key: K;
  label: ReactNode;
  icon?: ReactNode;
  disabled?: boolean;
}

interface SegmentedControlProps<K extends string> {
  label: string;
  segments: ReadonlyArray<Segment<K>>;
  value: K;
  onChange: (next: K) => void;
  stretch?: boolean;
  disabled?: boolean;
}

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

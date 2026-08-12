import { cssVars } from "../../theme/styleVars";
import styles from "./Toggle.module.css";

interface ToggleProps {
  on: boolean;
  disabled?: boolean;
  /** The tone the switch reads in when on, as a `var(--…)` reference. */
  tint: string;
  onChange: () => void;
  title?: string;
}

/**
 * A small on/off switch.
 *
 * The geometry props this used to take — width, height, knobSize, padding,
 * offColor, style — are gone: one caller existed and it passed none of them.
 */
export function Toggle({ on, disabled = false, tint, onChange, title }: ToggleProps) {
  return (
    <button
      type="button"
      onClick={onChange}
      aria-pressed={on}
      disabled={disabled}
      title={title}
      className={styles.toggle}
      style={cssVars({ "--switch-tint": tint })}
    >
      <span className={styles.knob} />
    </button>
  );
}

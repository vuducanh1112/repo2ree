import { cssVars } from "../../theme/styleVars";
import styles from "./Toggle.module.css";

interface ToggleProps {
  on: boolean;
  disabled?: boolean;
  ariaLabel: string;
  tint: string;
  onChange: () => void;
  title?: string;
}

export function Toggle({ on, disabled = false, ariaLabel, tint, onChange, title }: ToggleProps) {
  return (
    <button
      type="button"
      onClick={onChange}
      aria-pressed={on}
      aria-label={ariaLabel}
      disabled={disabled}
      data-ui="toggle"
      title={title}
      className={styles.toggle}
      style={cssVars({ "--switch-tint": tint })}
    >
      <span className={styles.knob} />
    </button>
  );
}

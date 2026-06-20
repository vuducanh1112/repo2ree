import type { CSSProperties, ReactNode } from "react";
import { Ic } from "../../shared/components/Icon";
import { lgPrimaryActionButton } from "../../theme/lightGlassTheme";
import { GlassCancelButton } from "./GlassCancelButton";

interface RunActionButtonProps {
  /** Visible label, e.g. "Run build" / "Building…" / "Re-build". */
  label: string;
  running: boolean;
  disabled: boolean;
  onRun: () => void;
  /** When provided, a Cancel button is shown alongside while running. */
  onCancel?: () => void;
  iconSize?: number;
  /** Icon shown when idle (defaults to the play triangle). */
  idleIcon?: (size: number) => ReactNode;
  /** Override the button style (defaults to the shared primary-action style). */
  style?: CSSProperties;
  title?: string;
}

/**
 * The single "run this assembly step" button used across every page (build,
 * evaluate, activation, SBOM, experiments, …). Centralising it keeps the
 * loading/spin behaviour consistent and — importantly — marks the icon
 * `aria-hidden` so the icon's <title> ("Play"/"Loading") never leaks into the
 * button's accessible name. The accessible name is exactly the visible label,
 * which is what tests select on.
 */
export function RunActionButton({
  label,
  running,
  disabled,
  onRun,
  onCancel,
  iconSize = 14,
  idleIcon = Ic.play,
  style,
  title,
}: RunActionButtonProps) {
  const button = (
    <button
      type="button"
      onClick={onRun}
      disabled={disabled}
      title={title}
      style={style ?? lgPrimaryActionButton(disabled)}
    >
      <span
        aria-hidden
        style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
      >
        {running ? Ic.loader(iconSize) : idleIcon(iconSize)}
      </span>
      {label}
    </button>
  );

  if (!onCancel) return button;

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", flexShrink: 0 }}>
      {button}
      {running && <GlassCancelButton onClick={onCancel} />}
    </div>
  );
}

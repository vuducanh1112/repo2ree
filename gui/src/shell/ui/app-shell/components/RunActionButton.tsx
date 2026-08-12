import type { ReactNode } from "react";
import { Button } from "../../shared/components/Button";
import { Ic } from "../../shared/components/Icon";
import { GlassCancelButton } from "./GlassCancelButton";
import styles from "./RunActionButton.module.css";

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
  title?: string;
  /** How the run reads: the shared blue primary, or tinted by the page's own
   * identity. `secondary` is the quieter inline run (an experiment row). */
  variant?: "primary" | "accent" | "secondary";
  /** The tone `accent` and a washed `secondary` are drawn in. */
  tint?: string;
  size?: "medium" | "small";
}

/**
 * The single "run this step" button used across every page (build,
 * evaluate, activation, SBOM, experiments, …). Centralising it keeps the
 * loading/spin behaviour consistent and — importantly — marks the icon
 * `aria-hidden` so the icon's <title> ("Play"/"Loading") never leaks into the
 * button's accessible name. The accessible name is exactly the visible label,
 * which is what tests select on.
 *
 * The `style` override this used to accept is gone. Callers that needed their
 * own colour now name it — `variant="accent"` with the page's tone — and every
 * other difference between the old overrides was a restatement of what `Button`
 * already does.
 */
export function RunActionButton({
  label,
  running,
  disabled,
  onRun,
  onCancel,
  iconSize = 14,
  idleIcon = Ic.play,
  title,
  variant = "primary",
  tint,
  size = "medium",
}: RunActionButtonProps) {
  const button = (
    <Button
      variant={variant}
      tint={tint}
      size={size}
      onClick={onRun}
      disabled={disabled}
      busy={running}
      title={title}
      icon={running ? Ic.loader(iconSize) : idleIcon(iconSize)}
    >
      {label}
    </Button>
  );

  if (!onCancel) return button;

  return (
    <div className={styles.pair}>
      {button}
      {running && <GlassCancelButton onClick={onCancel} />}
    </div>
  );
}

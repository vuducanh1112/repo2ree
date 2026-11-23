import type { ReactNode } from "react";
import { Button } from "../../shared/components/Button";
import { Ic } from "../../shared/components/Icon";
import { GlassCancelButton } from "./GlassCancelButton";
import styles from "./RunActionButton.module.css";

interface RunActionButtonProps {
  label: string;
  running: boolean;
  disabled: boolean;
  onRun: () => void;
  onCancel?: () => void;
  iconSize?: number;
  idleIcon?: (size: number) => ReactNode;
  title?: string;
  variant?: "primary" | "accent" | "secondary";
  tint?: string;
  size?: "medium" | "small";
}

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

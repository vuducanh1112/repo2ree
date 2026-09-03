import { type RunTickerTone, runTicker } from "@core/runs/runHud";
import { useReeQuery } from "@shell/data/ree/queries";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { placementReadout } from "@shell/ui/labs/labPresentation";
import type { ReactNode } from "react";
import { Ic } from "../../shared/components/Icon";
import styles from "./WorkspaceFooterBar.module.css";

interface WorkspaceFooterBarProps {
  provisioned: boolean;
  benchOpen: boolean;
  logsOpen: boolean;
  onBenchOpenChange: (open: boolean) => void;
  onLogsOpenChange: (open: boolean) => void;
}

/**
 * The ambient state strip under the canvas: the placement this REE runs on, and what
 * its runs are doing. Deliberately thinner and quieter than the WorkspaceStatusBar
 * above — that bar navigates, this one only reports. Each cell owns the resting
 * state of a console that opens at the canvas edge just above it, so the corners
 * stay clear until asked for.
 */
export function WorkspaceFooterBar({
  provisioned,
  benchOpen,
  logsOpen,
  onBenchOpenChange,
  onLogsOpenChange,
}: WorkspaceFooterBarProps) {
  const runsQuery = useReeRunsQuery();
  const ticker = runTicker(runsQuery.data ?? []);
  const reeQuery = useReeQuery();
  const placement = placementReadout(
    reeQuery.data?.workbenchLocation,
    reeQuery.data?.workbenchImage,
  );

  return (
    <section aria-label="Workbench status" className={styles.bar}>
      <FooterCell
        label="Workbench"
        detail={provisioned ? placement : "Awaiting workbench"}
        icon={Ic.package(13)}
        tone={provisioned ? "succeeded" : "idle"}
        open={benchOpen}
        onClick={() => onBenchOpenChange(!benchOpen)}
      />

      <div className={styles.spacer} />

      <FooterCell
        label="Logs"
        detail={ticker.detail}
        icon={Ic.terminal(13)}
        tone={ticker.tone}
        open={logsOpen}
        onClick={() => onLogsOpenChange(!logsOpen)}
      />
    </section>
  );
}

function FooterCell({
  label,
  detail,
  icon,
  tone,
  open,
  onClick,
}: {
  label: string;
  detail: string;
  icon: ReactNode;
  tone: RunTickerTone;
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className={styles.cell} aria-pressed={open} onClick={onClick}>
      <span aria-hidden className={styles.icon}>
        {icon}
      </span>
      <span className={styles.label}>{label}</span>
      <span className={styles.detail}>{detail}</span>
      <span aria-hidden className={styles.dot} data-tone={tone} />
    </button>
  );
}

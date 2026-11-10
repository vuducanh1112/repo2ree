import type { ReactNode } from "react";
import { Badge } from "../../shared/components/Badge";
import { Ic } from "../../shared/components/Icon";
import { Notice } from "../../shared/components/Notice";
import { Surface } from "../../shared/components/Surface";
import { cssVars } from "../../theme/styleVars";
import styles from "./ExperimentEnvironmentTargetCard.module.css";

interface ExperimentEnvironmentTargetCardProps {
  /** Workspace-relative path of the declared runtime, or "" if none yet. */
  experimentEnvironmentPath: string;
  experimentEnvironmentPathExists: boolean;
  icon: ReactNode;
  /** The page's tone, as a `var(--…)` reference. */
  tint: string;
  /** The chips under the readout: what this page checks about the target. */
  children: ReactNode;
}

/**
 * "Here is the experiment environment this step acts on" — the readout SBOM generation and
 * activation testing both open with. It was written twice, once per page, and
 * the two copies had already drifted apart in their icon sizing and their
 * missing-file wording.
 */
export function ExperimentEnvironmentTargetCard({
  experimentEnvironmentPath,
  experimentEnvironmentPathExists,
  icon,
  tint,
  children,
}: ExperimentEnvironmentTargetCardProps) {
  const ready = !!experimentEnvironmentPath && experimentEnvironmentPathExists;

  return (
    <Surface spacing="flush">
      <div className={styles.target}>
        <div className={styles.row}>
          <div aria-hidden className={styles.icon} style={cssVars({ "--target-tint": tint })}>
            {icon}
          </div>
          <div className={styles.body}>
            <div className={styles.kind}>ree.spec.experimentEnvironmentPath</div>
            <div
              className={styles.path}
              data-declared={experimentEnvironmentPath ? true : undefined}
            >
              {experimentEnvironmentPath || "No experiment environment selected yet"}
            </div>
          </div>
          <Badge tone={ready ? "success" : "warning"}>
            {ready ? "Ready" : "Needs experiment environment"}
          </Badge>
        </div>

        {experimentEnvironmentPath && !experimentEnvironmentPathExists && (
          <Notice tone="danger" icon={Ic.info(13)}>
            Selected runtime is not present in the current workspace files.
          </Notice>
        )}

        <div className={styles.chips}>{children}</div>
      </div>
    </Surface>
  );
}

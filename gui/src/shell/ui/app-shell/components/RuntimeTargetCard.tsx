import type { ReactNode } from "react";
import { Badge } from "../../shared/components/Badge";
import { Ic } from "../../shared/components/Icon";
import { Notice } from "../../shared/components/Notice";
import { Surface } from "../../shared/components/Surface";
import { cssVars } from "../../theme/styleVars";
import styles from "./RuntimeTargetCard.module.css";

interface RuntimeTargetCardProps {
  /** Workspace-relative path of the declared runtime, or "" if none yet. */
  runtimePath: string;
  runtimePathExists: boolean;
  icon: ReactNode;
  /** The page's tone, as a `var(--…)` reference. */
  tint: string;
  /** The chips under the readout: what this page checks about the target. */
  children: ReactNode;
}

/**
 * "Here is the runtime this step acts on" — the readout SBOM generation and
 * activation testing both open with. It was written twice, once per page, and
 * the two copies had already drifted apart in their icon sizing and their
 * missing-file wording.
 */
export function RuntimeTargetCard({
  runtimePath,
  runtimePathExists,
  icon,
  tint,
  children,
}: RuntimeTargetCardProps) {
  const ready = !!runtimePath && runtimePathExists;

  return (
    <Surface spacing="flush">
      <div className={styles.target}>
        <div className={styles.row}>
          <div aria-hidden className={styles.icon} style={cssVars({ "--target-tint": tint })}>
            {icon}
          </div>
          <div className={styles.body}>
            <div className={styles.kind}>ree.spec.runtime</div>
            <div className={styles.path} data-declared={runtimePath ? true : undefined}>
              {runtimePath || "No runtime selected yet"}
            </div>
          </div>
          <Badge tone={ready ? "success" : "warning"}>{ready ? "Ready" : "Needs runtime"}</Badge>
        </div>

        {runtimePath && !runtimePathExists && (
          <Notice tone="danger" icon={Ic.info(13)}>
            Selected runtime is not present in the current workspace files.
          </Notice>
        )}

        <div className={styles.chips}>{children}</div>
      </div>
    </Surface>
  );
}

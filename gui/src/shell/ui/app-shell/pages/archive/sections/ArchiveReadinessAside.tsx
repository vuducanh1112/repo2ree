import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { GlassPanel } from "@shell/ui/app-shell/components/GlassPageShell";
import { SummaryLine } from "@shell/ui/app-shell/components/SummaryLine";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import { archiveTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "../ArchivePage.module.css";

interface ArchiveReadinessAsideProps {
  buildDone: boolean;
  sbomDone: boolean;
  activationDone: boolean;
  isSealed: boolean;
  repo: ArchiveRepo;
  assignedId?: string;
}

function CheckRow({ label, done }: { label: string; done: boolean }) {
  return (
    <div className={styles.check} data-done={done || undefined}>
      <span aria-hidden className={styles.checkIcon}>
        {done ? Ic.check(14) : Ic.x(14)}
      </span>
      <span className={styles.checkLabel}>{label}</span>
    </div>
  );
}

export function ArchiveReadinessAside({
  buildDone,
  sbomDone,
  activationDone,
  isSealed,
  repo,
  assignedId,
}: ArchiveReadinessAsideProps) {
  const capstoneReady = buildDone && sbomDone && activationDone;

  return (
    <GlassPanel density="compact">
      <div className={styles.asideHead}>
        <span aria-hidden className={styles.asideIcon}>
          {Ic.shield(22)}
        </span>
        <h2 className={styles.asideTitle}>Deposit Readiness</h2>
      </div>

      <Surface spacing="flush" vars={{ "--archive-tint": archiveTone(repo.key) }}>
        <div className={styles.readout}>
          <div className={styles.readoutHead}>
            <span className={styles.readoutLabel}>Prerequisites</span>
            <Badge tone={capstoneReady ? "success" : "warning"}>
              {capstoneReady ? "Ready" : "Pending"}
            </Badge>
          </div>

          <div className={styles.checks}>
            <CheckRow label="Runtime built" done={buildDone} />
            <CheckRow label="SBOM generated" done={sbomDone} />
            <CheckRow label="Activation tested" done={activationDone} />
          </div>

          <SummaryLine
            label={repo.idLabel}
            value={
              assignedId ? (
                <span
                  className={styles.assignedId}
                  style={cssVars({ "--archive-tint": archiveTone(repo.key) })}
                >
                  {assignedId}
                </span>
              ) : (
                <span className={styles.unassigned}>Not assigned yet</span>
              )
            }
          />

          <SummaryLine
            label="Seal status"
            value={
              <Badge tone={isSealed ? "success" : "warning"}>
                {isSealed ? "Sealed" : "Not sealed"}
              </Badge>
            }
          />
        </div>
      </Surface>
    </GlassPanel>
  );
}

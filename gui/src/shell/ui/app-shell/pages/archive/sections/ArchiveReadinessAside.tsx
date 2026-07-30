import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { SummaryLine } from "@shell/ui/app-shell/components/SummaryLine";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgStatusBadge, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

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
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ color: done ? lgColors.success : lgColors.textMuted, display: "flex" }}>
        {done ? Ic.check(14) : Ic.x(14)}
      </span>
      <span
        style={{
          fontSize: 13,
          fontFamily: F.sans,
          color: done ? lgColors.text : lgColors.textMuted,
        }}
      >
        {label}
      </span>
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
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.shield(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Deposit Readiness</h2>
      </div>

      <div style={lgStyles.summaryBox}>
        <div style={lgStyles.asideHeader}>
          <span style={lgStyles.asideLabel}>Prerequisites</span>
          <span style={lgStatusBadge(capstoneReady)}>{capstoneReady ? "Ready" : "Pending"}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <CheckRow label="Runtime built" done={buildDone} />
          <CheckRow label="SBOM generated" done={sbomDone} />
          <CheckRow label="Activation tested" done={activationDone} />
        </div>

        <SummaryLine
          label={repo.idLabel}
          value={
            assignedId ? (
              <span style={{ fontFamily: F.mono, color: repo.color }}>{assignedId}</span>
            ) : (
              <span style={{ color: lgColors.textMuted }}>Not assigned yet</span>
            )
          }
        />

        <SummaryLine
          label="Seal status"
          value={<span style={lgStatusBadge(isSealed)}>{isSealed ? "Sealed" : "Not sealed"}</span>}
        />
      </div>
    </section>
  );
}

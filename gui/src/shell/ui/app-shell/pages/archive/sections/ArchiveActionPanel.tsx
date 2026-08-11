import type { ReeRunLogs } from "@core/ree/ReeTypes";
import type {
  ArchiveRepo,
  GenericReeStepParams,
  ReeStepRequirement,
} from "@core/ree-steps/stepTypes";
import { CollapsibleLogCard } from "@shell/ui/app-shell/components/CollapsibleLogCard";
import { RunActionButton } from "@shell/ui/app-shell/components/RunActionButton";
import { Ic } from "@shell/ui/shared/components/Icon";
import { archiveTone, translucent } from "@shell/ui/theme/appearance";
import { lgColors, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { MissingInputsBanner } from "../../../components/MissingInputsBanner";

interface ArchiveActionPanelProps {
  repo: ArchiveRepo;
  canRun: boolean;
  earned: boolean;
  running: boolean;
  missing: ReeStepRequirement[];
  logs: ReeRunLogs;
  onRun: (key: string, params: GenericReeStepParams) => void;
  getParam: (repoKey: string, paramKey: string) => string | boolean;
}

export function ArchiveActionPanel({
  repo,
  canRun,
  earned,
  running,
  missing,
  logs,
  onRun,
  getParam,
}: ArchiveActionPanelProps) {
  const tone = archiveTone(repo.key);
  const log = logs[repo.key];
  const hasMissing = missing.length > 0;
  const disabled = !canRun;

  const buttonLabel = running
    ? `Depositing to ${repo.label}…`
    : earned
      ? `Re-deposit to ${repo.label}`
      : `Deposit to ${repo.label}`;

  const buttonStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    width: "100%",
    padding: "11px 18px",
    borderRadius: 8,
    fontWeight: 800,
    fontSize: 13,
    fontFamily: F.sans,
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "all 0.18s",
    border: disabled ? "1px solid rgba(148, 163, 184, 0.34)" : `1px solid ${translucent(tone, 40)}`,
    background: disabled
      ? "rgba(241, 245, 249, 0.72)"
      : earned
        ? translucent(tone, 8)
        : `linear-gradient(135deg, ${tone}, ${translucent(tone, 80)})`,
    color: disabled ? lgColors.textMuted : earned ? tone : lgColors.white,
    boxShadow: disabled || earned ? "none" : `0 14px 30px ${translucent(tone, 20)}`,
  };

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color: tone, display: "flex" }}>{Ic.upload(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Deposit</h2>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <MissingInputsBanner missing={missing} />

        <RunActionButton
          label={buttonLabel}
          running={running}
          disabled={disabled}
          idleIcon={earned ? Ic.check : Ic.upload}
          style={buttonStyle}
          onRun={() =>
            canRun &&
            onRun(
              repo.key,
              Object.fromEntries(repo.params.map((p) => [p.key, getParam(repo.key, p.key)])),
            )
          }
        />

        {!hasMissing && (
          <span style={lgStyles.helper}>
            {earned
              ? `Already deposited — re-deposit to update the ${repo.label} record.`
              : `Submits this REE to ${repo.label} and records the returned ${repo.idLabel}.`}
          </span>
        )}

        <CollapsibleLogCard log={log} running={running} title="Deposit Log" maxHeight={260} />
      </div>
    </section>
  );
}

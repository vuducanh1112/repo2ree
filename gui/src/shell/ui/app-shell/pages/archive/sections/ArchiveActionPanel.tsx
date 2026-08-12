import type { ReeRunLogs } from "@core/ree/ReeTypes";
import type {
  ArchiveRepo,
  GenericReeStepParams,
  ReeStepRequirement,
} from "@core/ree-steps/stepTypes";
import { CollapsibleLogCard } from "@shell/ui/app-shell/components/CollapsibleLogCard";
import { GlassPanel } from "@shell/ui/app-shell/components/GlassPageShell";
import { RunActionButton } from "@shell/ui/app-shell/components/RunActionButton";
import { Ic } from "@shell/ui/shared/components/Icon";
import { archiveTone } from "@shell/ui/theme/appearance";
import { lgColors, lgStyles } from "@shell/ui/theme/lightGlassTheme";
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

  return (
    <GlassPanel density="compact">
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
          variant={earned ? "secondary" : "accent"}
          tint={tone}
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
    </GlassPanel>
  );
}

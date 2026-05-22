import type { ExecutionRunLogs } from "../../../../../../core/ree/ReeTypes";
import type {
  ArchiveRepo,
  GenericReeAssemblyParams,
  ReeAssemblyRequirement,
} from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgStyles } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
import { CollapsibleLogCard } from "../../../components/CollapsibleLogCard";

interface ArchiveActionPanelProps {
  repo: ArchiveRepo;
  canRun: boolean;
  earned: boolean;
  running: boolean;
  missing: ReeAssemblyRequirement[];
  logs: ExecutionRunLogs;
  onRun: (key: string, params: GenericReeAssemblyParams) => void;
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
    border: disabled ? "1px solid rgba(148, 163, 184, 0.34)" : `1px solid ${repo.color}66`,
    background: disabled
      ? "rgba(241, 245, 249, 0.72)"
      : earned
        ? `${repo.color}14`
        : `linear-gradient(135deg, ${repo.color}, ${repo.color}cc)`,
    color: disabled ? lgColors.textMuted : earned ? repo.color : lgColors.white,
    boxShadow: disabled || earned ? "none" : `0 14px 30px ${repo.color}33`,
  };

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color: repo.color, display: "flex" }}>{Ic.upload(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Deposit</h2>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {hasMissing && (
          <div
            style={{
              border: `1px solid ${lgColors.dangerBorder}`,
              background: "rgba(255, 241, 242, 0.7)",
              borderRadius: 8,
              padding: 10,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: lgColors.danger }}>
                Required inputs missing
              </span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {missing.map((item) => (
                <span
                  key={item.field}
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    color: lgColors.danger,
                    background: "rgba(255,255,255,0.55)",
                    border: `1px solid ${lgColors.dangerBorder}`,
                    borderRadius: 4,
                    padding: "2px 8px",
                  }}
                >
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            canRun &&
            onRun(
              repo.key,
              Object.fromEntries(repo.params.map((p) => [p.key, getParam(repo.key, p.key)])),
            )
          }
          style={buttonStyle}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : earned ? Ic.check(14) : Ic.upload(14)}
          </span>
          {buttonLabel}
        </button>

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

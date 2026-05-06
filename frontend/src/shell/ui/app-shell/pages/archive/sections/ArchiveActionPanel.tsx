import type { ExecutionRunLogs } from "../../../../../../core/ree/ReeTypes";
import type {
  ArchiveRepo,
  GenericReeAssemblyParams,
} from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import { C, F, S_SECTION_LABEL } from "../../../../theme/theme";
import { LogPanel } from "../../../components/logPanel";

interface ArchiveActionPanelProps {
  repo: ArchiveRepo;
  canRun: boolean;
  earned: boolean;
  running: boolean;
  logs: ExecutionRunLogs;
  onRun: (key: string, params: GenericReeAssemblyParams) => void;
  getParam: (repoKey: string, paramKey: string) => string | boolean;
}

export function ArchiveActionPanel({
  repo,
  canRun,
  earned,
  running,
  logs,
  onRun,
  getParam,
}: ArchiveActionPanelProps) {
  const log = logs[repo.key];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <button
        type="button"
        onClick={() =>
          canRun &&
          onRun(
            repo.key,
            Object.fromEntries(repo.params.map((p) => [p.key, getParam(repo.key, p.key)])),
          )
        }
        disabled={!canRun}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          padding: "11px",
          borderRadius: 9,
          background: !canRun ? C.surfaceAlt : earned ? repo.bg : repo.color,
          border: earned ? `1.5px solid ${repo.border}` : "none",
          color: !canRun ? C.textMuted : earned ? repo.color : "#fff",
          fontSize: 15,
          fontWeight: 700,
          fontFamily: F.sans,
          cursor: canRun ? "pointer" : "default",
          boxShadow: canRun && !earned ? `0 2px 12px ${repo.color}40` : "none",
          transition: "all 0.2s",
        }}
      >
        <span
          style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
        >
          {running ? Ic.loader(15) : earned ? Ic.check(15) : Ic.upload(15)}
        </span>
        {running
          ? `Depositing to ${repo.label}…`
          : earned
            ? `Re-deposit to ${repo.label}`
            : `Deposit to ${repo.label}`}
      </button>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ ...S_SECTION_LABEL, letterSpacing: 1.3, fontWeight: 600 }}>Output</div>
        <LogPanel log={log} running={running} />
      </div>
    </div>
  );
}

import {
  type BuildScriptSource,
  buildReadiness,
  buildSummaryStatusLabel,
  provenanceLabel,
  runtimeArtifactStatus,
  runtimeSummaryStatusLabel,
} from "../../../../../../core/ree-assembly/buildRuntimeUiState";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgReadout, lgStatusBadge, lgStyles } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
import { SummaryLine } from "../../../components/SummaryLine";

interface BuildSummaryAsideProps {
  scriptPath: string;
  source: BuildScriptSource | null;
  runtimePath: string;
  runtimePathExists: boolean;
  includeRuntime: boolean;
  runtimeSize: string | null;
  runDone: boolean;
}

export function BuildSummaryAside({
  scriptPath,
  source,
  runtimePath,
  runtimePathExists,
  includeRuntime,
  runtimeSize,
  runDone,
}: BuildSummaryAsideProps) {
  const summaryLabel = buildSummaryStatusLabel({ runDone, hasScript: !!scriptPath });
  const runtimeStatus = runtimeArtifactStatus({
    hasRuntime: !!runtimePath,
    runtimePathExists,
    includeRuntime,
  });
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.cpu(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Build Summary</h2>
      </div>
      <div style={lgStyles.summaryBox}>
        <div style={lgStyles.overviewHeader}>
          <span style={lgStyles.overviewLabel}>Overview</span>
          <span style={lgStatusBadge(runDone)}>{summaryLabel}</span>
        </div>
        <SummaryLine label="Script" value={scriptPath || "Not set"} />
        <SummaryLine label="Source" value={provenanceLabel(scriptPath ? source : null)} />
        <SummaryLine label="Runtime artifact" value={runtimePath || "Not selected"} />
        <SummaryLine label="Runtime status" value={runtimeSummaryStatusLabel(runtimeStatus)} />
        <SummaryLine label="Runtime size" value={runtimeSize || "—"} />
        <SummaryLine label="Last build" value={runDone ? "Completed" : "Not run yet"} />
      </div>
    </section>
  );
}

interface BuildReadinessAsideProps {
  hasScript: boolean;
  hasRuntime: boolean;
  runtimePathExists: boolean;
  runDone: boolean;
}

export function BuildReadinessAside({
  hasScript,
  hasRuntime,
  runtimePathExists,
  runDone,
}: BuildReadinessAsideProps) {
  const r = buildReadiness({ hasScript, hasRuntime, runtimePathExists, runDone });
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={lgStyles.readinessHeader}>
        <span>Build Readiness</span>
        <span style={{ color: lgColors.blue, fontFamily: F.mono }}>{r.percent}%</span>
      </div>
      <div style={lgStyles.progressTrack}>
        <div style={{ ...lgStyles.progressFill, width: `${r.percent}%` }} />
      </div>
      <div style={lgStyles.statGrid}>
        <Stat label="Script" done={r.hasScript} />
        <Stat label="Runtime" done={r.runtimeReady} />
        <Stat label="Built" done={r.runDone} />
        <div style={lgReadout(lgStyles.statReadout)}>
          <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Checks</span>
          <strong style={{ color: lgColors.text, fontSize: 18 }}>
            {r.done}/{r.total}
          </strong>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, done }: { label: string; done: boolean }) {
  return (
    <div style={lgReadout(lgStyles.statReadout)}>
      <span style={{ color: lgColors.textMuted, fontSize: 11 }}>{label}</span>
      <strong style={{ color: lgColors.text, fontSize: 18 }}>{done ? "✓" : "—"}</strong>
    </div>
  );
}

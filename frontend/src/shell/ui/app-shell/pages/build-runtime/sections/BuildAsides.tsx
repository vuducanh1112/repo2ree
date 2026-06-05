import {
  type BuildScriptSource,
  buildReadiness,
  buildSummaryStatusLabel,
  provenanceLabel,
  runtimeArtifactStatus,
  runtimeSummaryStatusLabel,
} from "../../../../../../core/ree-assembly/buildRuntimeUiState";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgStatusBadge, lgStyles } from "../../../../theme/lightGlassTheme";
import { ReadinessPanel } from "../../../components/ReadinessPanel";
import { SummaryLine } from "../../../components/SummaryLine";
import { SummaryPanel } from "../../../components/SummaryPanel";
import { ReadinessStat } from "../../runtime-environment/ReadinessStat";

interface BuildSummaryAsideProps {
  scriptPath: string;
  source: BuildScriptSource | null;
  runtimePath: string;
  runtimePathExists: boolean;
  runtimeSize: string | null;
  runDone: boolean;
}

export function BuildSummaryAside({
  scriptPath,
  source,
  runtimePath,
  runtimePathExists,
  runtimeSize,
  runDone,
}: BuildSummaryAsideProps) {
  const summaryLabel = buildSummaryStatusLabel({ runDone, hasScript: !!scriptPath });
  const runtimeStatus = runtimeArtifactStatus({
    hasRuntime: !!runtimePath,
    runtimePathExists,
  });
  return (
    <SummaryPanel title="Build Summary" icon={Ic.cpu(22)} iconColor={lgColors.cyan}>
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
    </SummaryPanel>
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
    <ReadinessPanel title="Build Readiness" percent={r.percent} done={r.done} total={r.total}>
      <ReadinessStat label="Script" done={r.hasScript} />
      <ReadinessStat label="Runtime" done={r.runtimeReady} />
      <ReadinessStat label="Built" done={r.runDone} />
    </ReadinessPanel>
  );
}

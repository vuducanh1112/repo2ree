import { activationReadiness } from "../../../../../../core/ree-assembly/activationUiState";
import { Ic } from "../../../../shared/components/Icon";
import { lgPageColors, lgStatusBadge, lgStyles } from "../../../../theme/lightGlassTheme";
import { ReadinessPanel } from "../../../components/ReadinessPanel";
import { SummaryLine } from "../../../components/SummaryLine";
import { SummaryPanel } from "../../../components/SummaryPanel";
import { ReadinessStat } from "../../runtime-environment/ReadinessStat";

interface ActivationSummaryAsideProps {
  runtimePath: string;
  runtimePathExists: boolean;
  sbomPath: string;
  sbomPathExists: boolean;
  scriptPath: string;
  scriptPresent: boolean;
  runDone: boolean;
}

export function ActivationSummaryAside({
  runtimePath,
  runtimePathExists,
  sbomPath,
  sbomPathExists,
  scriptPath,
  scriptPresent,
  runDone,
}: ActivationSummaryAsideProps) {
  return (
    <SummaryPanel
      title="Activation Summary"
      icon={Ic.shield(22)}
      iconColor={lgPageColors.runtimeEnv}
    >
      <div style={lgStyles.overviewHeader}>
        <span style={lgStyles.overviewLabel}>Overview</span>
        <span style={lgStatusBadge(runDone)}>{runDone ? "Verified" : "Pending"}</span>
      </div>
      <SummaryLine label="Runtime artifact" value={runtimePath || "Not selected"} />
      <SummaryLine label="Runtime file" value={runtimePathExists ? "Present" : "Missing"} />
      <SummaryLine label="Activation script" value={scriptPath || "Not attached"} />
      <SummaryLine
        label="Script file"
        value={scriptPresent ? "Present" : scriptPath ? "Missing" : "—"}
      />
      <SummaryLine label="SBOM path" value={sbomPath || "Not generated"} />
      <SummaryLine
        label="SBOM file"
        value={sbomPathExists ? "Present" : sbomPath ? "Missing" : "—"}
      />
      <SummaryLine label="Last verification" value={runDone ? "Passed" : "Not run yet"} />
    </SummaryPanel>
  );
}

interface ActivationReadinessAsideProps {
  runtimePath: string;
  runtimePathExists: boolean;
  scriptPath: string;
  scriptPresent: boolean;
  runDone: boolean;
}

export function ActivationReadinessAside({
  runtimePath,
  runtimePathExists,
  scriptPath,
  scriptPresent,
  runDone,
}: ActivationReadinessAsideProps) {
  const r = activationReadiness({
    hasRuntime: !!runtimePath,
    runtimePathExists,
    hasScript: !!scriptPath,
    scriptPresent,
    runDone,
  });

  return (
    <ReadinessPanel title="Activation Readiness" percent={r.percent} done={r.done} total={r.total}>
      <ReadinessStat label="Runtime" done={r.hasRuntime} />
      <ReadinessStat label="File" done={r.runtimePathExists} />
      <ReadinessStat label="Script" done={r.hasScript && r.scriptPresent} />
      <ReadinessStat label="Verified" done={r.runDone} />
    </ReadinessPanel>
  );
}

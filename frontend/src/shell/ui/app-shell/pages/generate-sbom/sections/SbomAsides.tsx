import {
  runtimeArtifactStatus,
  runtimeSummaryStatusLabel,
} from "../../../../../../core/ree-assembly/buildRuntimeUiState";
import { sbomReadiness } from "../../../../../../core/ree-assembly/sbomUiState";
import type { FileTreeNode } from "../../../../../../core/workspace/FileTree";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgStatusBadge, lgStyles } from "../../../../theme/lightGlassTheme";
import { ReadinessPanel } from "../../../components/ReadinessPanel";
import { SummaryLine } from "../../../components/SummaryLine";
import { SummaryPanel } from "../../../components/SummaryPanel";
import { ReadinessStat } from "../../runtime-environment/ReadinessStat";

interface SbomSummaryAsideProps {
  runtimePath: string;
  runtimePathExists: boolean;
  sbomPath: string;
  sbomNode: FileTreeNode | null;
  pkgCount: number | null;
  sbomFormat: string | null;
  runDone: boolean;
}

export function SbomSummaryAside({
  runtimePath,
  runtimePathExists,
  sbomPath,
  sbomNode,
  pkgCount,
  sbomFormat,
  runDone,
}: SbomSummaryAsideProps) {
  const runtimeStatus = runtimeArtifactStatus({
    hasRuntime: !!runtimePath,
    runtimePathExists,
  });
  return (
    <SummaryPanel title="SBOM Summary" icon={Ic.package(22)} iconColor={lgColors.success}>
      <div style={lgStyles.overviewHeader}>
        <span style={lgStyles.overviewLabel}>Overview</span>
        <span style={lgStatusBadge(!!sbomPath)}>{sbomPath ? "Attached" : "Missing"}</span>
      </div>
      <SummaryLine label="Runtime artifact" value={runtimePath || "Not selected"} />
      <SummaryLine label="Runtime file" value={runtimePathExists ? "Present" : "Missing"} />
      <SummaryLine label="Runtime bundle" value={runtimeSummaryStatusLabel(runtimeStatus)} />
      <SummaryLine label="SBOM path" value={sbomPath || "Not generated"} />
      <SummaryLine label="SBOM file" value={sbomNode ? "Present" : sbomPath ? "Missing" : "—"} />
      <SummaryLine label="Format" value={sbomFormat || "—"} />
      <SummaryLine label="Packages" value={pkgCount === null ? "—" : String(pkgCount)} />
      <SummaryLine label="Last run" value={runDone ? "Completed" : "Not run yet"} />
    </SummaryPanel>
  );
}

interface SbomReadinessAsideProps {
  runtimePath: string;
  runtimePathExists: boolean;
  sbomPath: string;
}

export function SbomReadinessAside({
  runtimePath,
  runtimePathExists,
  sbomPath,
}: SbomReadinessAsideProps) {
  const r = sbomReadiness({
    hasRuntime: !!runtimePath,
    runtimePathExists,
    hasSbom: !!sbomPath,
  });
  return (
    <ReadinessPanel title="SBOM Readiness" percent={r.percent} done={r.done} total={r.total}>
      <ReadinessStat label="Runtime" done={r.hasRuntime} />
      <ReadinessStat label="File" done={r.runtimePathExists} />
      <ReadinessStat label="SBOM" done={r.hasSbom} />
    </ReadinessPanel>
  );
}

import { resolvedRuntimePath } from "@core/ree-steps/buildRuntimeUiState";
import {
  findSbomArtifact,
  isRuntimeTarballPath,
  resolvedSbomPath,
  summarizeSbom,
} from "@core/ree-steps/sbomUiState";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { lgPageRoot, lgStatusBadge, pageIconTint } from "@shell/ui/theme/lightGlassTheme";
import { useMemo } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import { stepIcon } from "../../stepIcons";
import type { StepPageProps } from "../sharedStepUi";
import { CrossCheckCard, RuntimeScanTargetCard, SbomOutputCard } from "./sections";

const SBOM_PAGE_COLOR = "#16a34a";

export function PageGenerateSbom({
  step,
  ree,
  workspaceFiles,
  reeFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGoFields,
  missing,
  params,
}: StepPageProps) {
  const files = workspaceFiles || [];

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);

  // The runtime is scanned where the build left it, in the workspace; the SBOM
  // that comes back is REE evidence and lives in artifacts/, so it is found
  // among the REE's own files rather than in the materialized tree.
  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = findSbomArtifact(reeFiles, sbomPath);
  const sbomSummary = useMemo(() => summarizeSbom(sbomNode), [sbomNode]);
  const sbomReady = !!sbomPath && !!sbomNode;

  const IC = stepIcon(step.iconKey);
  const disabled = running || missing.length > 0 || !runtimePathExists;

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={IC(24)}
        iconTint={pageIconTint(SBOM_PAGE_COLOR)}
        title={step.label}
        subtitle={step.desc}
        badges={
          <>
            <span style={lgStatusBadge(sbomReady)}>
              {sbomReady ? "SBOM ready" : "SBOM pending"}
            </span>
            {badge && <OutcomeBadge badge={badge} />}
          </>
        }
        right={
          <RunActionButton
            label={running ? "Generating…" : runDone ? "Regenerate" : "Generate"}
            running={running}
            disabled={disabled}
            onRun={() => onRun(step.key, params as ReeStepRunParams<"sbom">)}
            onCancel={() => onCancel?.(step.key)}
          />
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <RuntimeScanTargetCard
          runtimePath={runtimePath}
          runtimePathExists={runtimePathExists}
          runtimeIsTarball={runtimeIsTarball}
          color={SBOM_PAGE_COLOR}
        />

        <SbomOutputCard
          color={SBOM_PAGE_COLOR}
          sbomPath={sbomPath}
          sbomFilePresent={!!sbomNode}
          pkgCount={sbomSummary.pkgCount}
          sbomFormat={sbomSummary.format}
        />

        <CrossCheckCard sbomReady={sbomReady} color={SBOM_PAGE_COLOR} />

        <CollapsibleLogCard log={log} running={running} title={ts ? "SBOM log" : "SBOM logs"} />
      </div>
    </div>
  );
}

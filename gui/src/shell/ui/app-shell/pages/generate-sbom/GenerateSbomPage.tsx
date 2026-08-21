import { PAGE } from "@core/app-shell/pages";
import { resolvedRuntimePath } from "@core/ree-steps/buildRuntimeUiState";
import {
  findSbomArtifact,
  isRuntimeTarballPath,
  resolvedSbomPath,
  summarizeSbom,
} from "@core/ree-steps/sbomUiState";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { Badge } from "@shell/ui/shared/components/Badge";
import { stageTone } from "@shell/ui/theme/appearance";
import { useMemo } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPageShell } from "../../components/GlassPageShell";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import { stepIcon } from "../../stepIcons";
import type { StepPageProps } from "../sharedStepUi";
import styles from "./GenerateSbomPage.module.css";
import { CrossCheckCard, RuntimeScanTargetCard, SbomOutputCard } from "./sections";

const SBOM_PAGE_COLOR = stageTone(PAGE.SBOM);

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

  const runtimePath = resolvedRuntimePath(ree.spec.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);

  // The runtime is scanned where the build left it, in the workspace; the SBOM
  // that comes back is REE evidence and lives in artifacts/, so it is found
  // among the REE's own files rather than in the materialized tree.
  const sbomPath = resolvedSbomPath(ree.spec.sbom);
  const sbomNode = findSbomArtifact(reeFiles, sbomPath);
  const sbomSummary = useMemo(() => summarizeSbom(sbomNode), [sbomNode]);
  const sbomReady = !!sbomPath && !!sbomNode;

  const IC = stepIcon(step.iconKey);
  const disabled = running || missing.length > 0 || !runtimePathExists;

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={IC(24)}
        tint={SBOM_PAGE_COLOR}
        title={step.label}
        subtitle={step.desc}
        badges={
          <>
            <Badge tone={sbomReady ? "success" : "warning"}>
              {sbomReady ? "SBOM ready" : "SBOM pending"}
            </Badge>
            {badge && <OutcomeBadge outcome={badge} />}
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

      <div className={styles.stack}>
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
    </GlassPageShell>
  );
}

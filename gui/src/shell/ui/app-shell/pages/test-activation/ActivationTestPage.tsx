import { PAGE } from "@core/app-shell/pages";
import {
  activationFooterHint,
  activationRunLabel,
  canRunActivation,
} from "@core/ree-steps/activationUiState";
import { resolvedExperimentEnvironmentPath } from "@core/ree-steps/buildExperimentEnvironmentUiState";
import { findSbomArtifact, resolvedSbomPath } from "@core/ree-steps/sbomUiState";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import { findFileByWorkspacePath, workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { stageTone } from "@shell/ui/theme/appearance";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPageShell } from "../../components/GlassPageShell";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { GlassSubPanel } from "../../components/GlassSubPanel";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import type { StepPageProps } from "../sharedStepUi";
import styles from "./ActivationTestPage.module.css";
import { ActivationTargetCard } from "./sections";

const ACTIVATION_PAGE_COLOR = stageTone(PAGE.ACTIVATION);

/** What the activation test runs inside the experiment environment: a command that does nothing. */
const NOTHING = "true";

export function PageTestActivation({
  step,
  ree,
  workspaceFiles,
  reeFiles,
  log,
  running,
  runDone,
  runFailed,
  badge,
  ts,
  onRun,
  onCancel,
  onGoFields,
  missing,
  params,
}: StepPageProps) {
  const files = workspaceFiles || [];
  const { data: templates } = useScriptTemplates();

  // The activation is the activate script the build page writes, run alone: it has no script of its own.
  const activatePath = templates?.activate_experiment_environment.path ?? "";
  const activateContent = activatePath
    ? (findFileByWorkspacePath(files, activatePath)?.content ?? "")
    : "";

  const experimentEnvironmentPath = resolvedExperimentEnvironmentPath(
    ree.spec.experimentEnvironmentPath,
  );
  const experimentEnvironmentPathExists = experimentEnvironmentPath
    ? workspaceFileExists(files, experimentEnvironmentPath)
    : false;
  const sbomPath = resolvedSbomPath(ree.spec.sbom);
  const sbomPathExists = !!findSbomArtifact(reeFiles, sbomPath);

  const activationParams: ReeStepRunParams<"activation"> = params as ReeStepRunParams<"activation">;

  const canRun = canRunActivation({
    running,
    hasMissing: missing.length > 0,
    experimentEnvironmentPathExists,
  });
  const activationReady = runDone && !runFailed && canRun;
  const command = activatePath ? `sh ${activatePath} ${NOTHING}` : "";

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.shield(24)}
        tint={ACTIVATION_PAGE_COLOR}
        title="Test Activation"
        subtitle="Run the activation alone: it enters the experiment environment and hands over, as it does for every experiment."
        badges={
          <>
            {activatePath && (
              <Badge tone="info" flavor="code">
                {activatePath}
              </Badge>
            )}
            <Badge tone={activationReady ? "success" : "warning"}>
              {activationReady ? "Activation ready" : "Activation pending"}
            </Badge>
            {badge && <OutcomeBadge outcome={badge} />}
          </>
        }
        right={
          <div className={styles.headerActions}>
            {runDone && ts && <LastRunStamp label="Last tested" ts={ts} />}
            <RunActionButton
              label={activationRunLabel({ running, runDone })}
              running={running}
              disabled={!canRun}
              onRun={() => onRun(step.key, activationParams)}
              onCancel={onCancel ? () => onCancel(step.key) : undefined}
            />
          </div>
        }
      />

      <div className={styles.stack}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.shield(19)}
            tint={ACTIVATION_PAGE_COLOR}
            title="What Runs"
            subtitle="The activate experiment environment script, written on the Build Experiment Environment page, around a command that does nothing. Experiments run only while this activation's evidence is current."
          />
          <div className={styles.section}>
            {command && <code className={styles.command}>{command}</code>}
            {activateContent ? (
              <figure className={styles.figure} aria-label="Activate experiment environment script">
                <pre className={styles.script}>{activateContent}</pre>
              </figure>
            ) : (
              <p className={styles.empty}>
                No activate experiment environment script yet: write one on the Build Experiment
                Environment page.
              </p>
            )}
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.cpu(19)}
            tint={ACTIVATION_PAGE_COLOR}
            title="Experiment Environment Under Test"
            subtitle="The activation enters the experiment environment artifact from Build Experiment environment, with the inventory context from Generate SBOM."
          />

          <ActivationTargetCard
            experimentEnvironmentPath={experimentEnvironmentPath}
            experimentEnvironmentPathExists={experimentEnvironmentPathExists}
            sbomPath={sbomPath}
            sbomPathExists={sbomPathExists}
          />
        </GlassSubPanel>

        <GlassSubPanel>
          <CollapsibleLogCard
            log={log}
            running={running}
            title={ts ? "Activation log" : "Activation logs"}
          />
        </GlassSubPanel>

        <GlassPanelFooter bar>{activationFooterHint({ runDone, runFailed })}</GlassPanelFooter>
      </div>
    </GlassPageShell>
  );
}

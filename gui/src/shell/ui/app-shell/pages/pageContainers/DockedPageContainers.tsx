import { PAGE } from "@core/app-shell/pages";
import { useReeId } from "@shell/data/apiRuntime";
import { useStepPageController } from "../../hooks/useStepPageController";
import {
  PageBuildRuntime,
  PageExperiments,
  PageGenerateSbom,
  PageHardwareBom,
  PageMetadataEntry,
  PageRepoAnalysis,
  PageTestActivation,
  type StepPageProps,
} from "../index";
import { type AppShellPageContainerProps, ContentSection, useStepRunLogEntry } from "./shared";

const STEP_PAGE_COMPONENTS: Record<string, (props: StepPageProps) => JSX.Element> = {
  evaluate: (props) => <PageRepoAnalysis {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSbom {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

export function MetadataPageContainer({
  reeIntent,
  stepRuns,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = stepRuns;

  if (page !== PAGE.METADATA) {
    return null;
  }

  return (
    <PageMetadataEntry
      reeSpec={reeSpec}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      onReeChange={commands.setReeSpec}
      onLockedChange={commands.setLocked}
      onGoPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function ExperimentsPageContainer({
  reeIntent,
  stepRuns,
  uiChrome,
  commands,
  workspaceRemote,
}: AppShellPageContainerProps) {
  const reeId = useReeId();
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = stepRuns;
  const { workspaceFiles } = workspaceRemote;

  if (page !== PAGE.EXPERIMENTS) {
    return null;
  }

  return (
    <PageExperiments
      reeId={reeId}
      reeSpec={reeSpec}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      workspaceFiles={workspaceFiles}
      onReeChange={commands.setReeSpec}
      onGoPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onBeforeRun={commands.flushReeIntent}
      onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
    />
  );
}

export function HardwareBomPageContainer({
  ree,
  stepRuns,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const reeId = useReeId();
  const { page, focusedField, locked } = uiChrome;
  const { badges, actionStates, timestamps } = stepRuns;
  const hbomLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.hbom,
    fallbackTimestamp: timestamps.hbom,
  });

  if (page !== PAGE.HBOM) {
    return null;
  }

  return (
    <PageHardwareBom
      ree={ree}
      locked={locked}
      badges={badges}
      log={hbomLog}
      running={actionStates.hbom === "loading"}
      runDone={!!badges.hbom}
      ts={timestamps.hbom}
      focusedField={focusedField}
      onReeSpecChange={commands.setReeSpec}
      onLockedChange={commands.setLocked}
      onGoPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onRun={commands.onRunStep}
      onCancel={commands.onCancelAction}
    />
  );
}

export function StepPageContainer(props: AppShellPageContainerProps) {
  const { ree, workspaceRemote, stepRuns, commands, currentReeFiles } = props;
  const { badges } = stepRuns;
  const { workspaceFiles, workspaceSourceState, artifactStatus } = workspaceRemote;

  const stepPageController = useStepPageController(props);

  if (!stepPageController) {
    return null;
  }

  const {
    step,
    log,
    running,
    runDone,
    runFailed,
    badge,
    ts,
    missing,
    params,
    setParam,
    goToRequirements,
  } = stepPageController;

  const StepPageComponent = STEP_PAGE_COMPONENTS[step.key];
  if (!StepPageComponent) {
    return null;
  }

  return (
    <ContentSection>
      <StepPageComponent
        step={step}
        ree={ree}
        badges={badges}
        workspaceFiles={workspaceFiles}
        reeFiles={currentReeFiles}
        workspaceSourceState={workspaceSourceState}
        artifactStatus={artifactStatus}
        evaluationState={stepRuns.evaluationState}
        log={log}
        running={running}
        runDone={runDone}
        runFailed={runFailed}
        badge={badge}
        ts={ts}
        onRun={commands.onRunStep}
        onCancel={commands.onCancelAction}
        onGo={commands.setPage}
        onGoFields={goToRequirements}
        onReeSpecChange={commands.setReeSpec}
        onArtifactStatusChange={commands.setArtifactStatus}
        onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
        onEvaluationStateChange={commands.setEvaluationState}
        onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
        missing={missing}
        params={params}
        setParam={setParam}
      />
    </ContentSection>
  );
}

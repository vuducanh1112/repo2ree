import { isSuccessfulStepOutcome } from "@core/ree/ReeTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useStepRunLogEntry } from "@shell/state/ree-editor/step-runs/useStepRunLogEntry";
import { type ComponentType, type LazyExoticComponent, lazy } from "react";
import { useStepPageController } from "../../hooks/useStepPageController";
import type { StepPageProps } from "../sharedStepUi";
import type {
  ExperimentsPageContainerProps,
  HardwareBomPageContainerProps,
  MetadataPageContainerProps,
  StepPageContainerProps,
} from "./controllerContracts";
import { ContentSection } from "./shared";

const PageMetadataEntry = lazy(() =>
  import("../metadata/MetadataPage").then(({ PageMetadataEntry: Page }) => ({ default: Page })),
);
const PageExperiments = lazy(() =>
  import("../experiments/ExperimentsPage").then(({ PageExperiments: Page }) => ({ default: Page })),
);
const PageHardwareBom = lazy(() =>
  import("../hardware-bom/HardwareBomPage").then(({ PageHardwareBom: Page }) => ({
    default: Page,
  })),
);
const PageRepoAnalysis = lazy(() =>
  import("../repo-analysis/RepoAnalysisPage").then(({ PageRepoAnalysis: Page }) => ({
    default: Page,
  })),
);
const PageBuildRuntime = lazy(() =>
  import("../build-runtime/BuildRuntimePage").then(({ PageBuildRuntime: Page }) => ({
    default: Page,
  })),
);
const PageGenerateSbom = lazy(() =>
  import("../generate-sbom/GenerateSbomPage").then(({ PageGenerateSbom: Page }) => ({
    default: Page,
  })),
);
const PageTestActivation = lazy(() =>
  import("../test-activation/ActivationTestPage").then(({ PageTestActivation: Page }) => ({
    default: Page,
  })),
);

const STEP_PAGE_COMPONENTS: Record<string, LazyExoticComponent<ComponentType<StepPageProps>>> = {
  evaluate: PageRepoAnalysis,
  build: PageBuildRuntime,
  sbom: PageGenerateSbom,
  activation: PageTestActivation,
};

export function MetadataPageContainer({
  reeIntent,
  stepRuns,
  uiChrome,
  commands,
}: MetadataPageContainerProps) {
  const { focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const badges = stepRuns.badges ?? {};

  return (
    <PageMetadataEntry
      reeSpec={reeSpec}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      onReeChange={commands.setReeSpec}
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
}: ExperimentsPageContainerProps) {
  const reeId = useReeId();
  const { focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const badges = stepRuns.badges ?? {};
  const { workspaceFiles } = workspaceRemote;

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
}: HardwareBomPageContainerProps) {
  const reeId = useReeId();
  const { focusedField, locked } = uiChrome;
  const badges = stepRuns.badges ?? {};
  const actionStates = stepRuns.actionStates ?? {};
  const timestamps = stepRuns.timestamps ?? {};
  const activeRunIds = stepRuns.activeRunIds ?? {};
  const hbomLog = useStepRunLogEntry({
    reeId,
    runId: activeRunIds.hbom,
    fallbackTimestamp: timestamps.hbom,
  });

  return (
    <PageHardwareBom
      ree={ree}
      locked={locked}
      badges={badges}
      log={hbomLog}
      running={actionStates.hbom === "loading"}
      runDone={isSuccessfulStepOutcome(badges.hbom)}
      ts={timestamps.hbom}
      focusedField={focusedField}
      onReeSpecChange={commands.setReeSpec}
      onGoPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onRun={commands.onRunStep}
      onCancel={commands.onCancelAction}
    />
  );
}

export function StepPageContainer(props: StepPageContainerProps) {
  const { ree, workspaceRemote, stepRuns, commands, currentReeFiles } = props;
  const badges = stepRuns.badges ?? {};
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
        evaluationState={ree.evaluation}
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
        onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
        missing={missing}
        params={params}
        setParam={setParam}
      />
    </ContentSection>
  );
}

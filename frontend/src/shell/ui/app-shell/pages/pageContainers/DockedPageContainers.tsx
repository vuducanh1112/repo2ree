import { useApiRuntime } from "@shell/data/apiRuntime";
import { useAssemblyStepPageController } from "../../hooks/useAssemblyStepPageController";
import { PAGE } from "../../state/pages";
import {
  type AssemblyPageProps,
  PageBuildRuntime,
  PageEvaluate,
  PageExperiments,
  PageHardwareBom,
  PageMetadataEntry,
  PageTestActivation,
} from "../index";
import { type AppShellPageContainerProps, ContentSection, useAssemblyRunLogEntry } from "./shared";

const ASSEMBLY_PAGE_COMPONENTS: Record<string, (props: AssemblyPageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  // sbom opens as a compact floating hub panel (SbomHubPanel), not a docked page.
  activation: (props) => <PageTestActivation {...props} />,
};

export function MetadataPageContainer({
  reeIntent,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = assemblyRun;

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
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function ExperimentsPageContainer({
  reeIntent,
  assemblyRun,
  uiChrome,
  commands,
  workspaceRemote,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = assemblyRun;
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
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onBeforeRun={commands.flushReeIntent}
      onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
    />
  );
}

export function HardwareBomPageContainer({
  ree,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField, locked } = uiChrome;
  const { badges, actionStates, timestamps } = assemblyRun;
  const hbomLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.hbom,
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
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onRun={commands.onRunAssemblyStep}
      onCancel={commands.onCancelAction}
    />
  );
}

export function AssemblyPageContainer(props: AppShellPageContainerProps) {
  const { ree, workspaceRemote, assemblyRun, commands } = props;
  const { badges } = assemblyRun;
  const { workspaceFiles, workspaceSourceState, artifactStatus } = workspaceRemote;

  const assemblyPageController = useAssemblyStepPageController(props);

  if (!assemblyPageController) {
    return null;
  }

  const {
    assemblyStep,
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
  } = assemblyPageController;

  const AssemblyPageComponent = ASSEMBLY_PAGE_COMPONENTS[assemblyStep.key];
  if (!AssemblyPageComponent) {
    return null;
  }

  return (
    <ContentSection>
      <AssemblyPageComponent
        assemblyStep={assemblyStep}
        ree={ree}
        badges={badges}
        workspaceFiles={workspaceFiles}
        workspaceSourceState={workspaceSourceState}
        artifactStatus={artifactStatus}
        evaluationState={assemblyRun.evaluationState}
        log={log}
        running={running}
        runDone={runDone}
        runFailed={runFailed}
        badge={badge}
        ts={ts}
        onRun={commands.onRunAssemblyStep}
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

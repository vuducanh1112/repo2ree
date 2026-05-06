import type { SourceUploadCommit } from "../../../../core/ree/ReeTypes";
import { useApiRuntime } from "../../../../data/apiRuntime";
import { PAGE } from "../../../../shell/ui/app-shell/state/pages";
import { useAssemblyStepPageController } from "../../hooks/useAssemblyStepPageController";
import {
  type AssemblyPageProps,
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageHardwareBom,
  PageMetadataEntry,
  PageTestActivation,
  SourceAcquisitionPage,
} from "../index";
import { type AppShellPageContainerProps, ContentSection, useAssemblyRunLogEntry } from "./shared";

const ASSEMBLY_PAGE_COMPONENTS: Record<string, (props: AssemblyPageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

export function SourcePageContainer({
  ree,
  inclusionState,
  reeDraft,
  workspaceRemote,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked, repoMode } = reeDraft;
  const { badges, actionStates } = assemblyRun;
  const sourceLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.source,
    fallbackTimestamp: assemblyRun.timestamps.source,
  });

  if (page !== PAGE.SOURCE) {
    return null;
  }

  return (
    <SourceAcquisitionPage
      ree={ree}
      inclusionState={inclusionState}
      workspaceSourceState={workspaceRemote.workspaceSourceState}
      locked={locked}
      repoMode={repoMode}
      badges={badges}
      actionStates={actionStates}
      log={sourceLog}
      running={actionStates.source === "loading"}
      focusedField={focusedField}
      onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
      onRepoModeChange={commands.setRepoMode}
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onDownloadSource={commands.onDownloadSourceFiles}
      onCancelSource={() => commands.onCancelAction("source")}
      onWorkspaceUpload={(payload: SourceUploadCommit) => commands.onWorkspaceUpload(payload)}
      onRemoveWorkspaceSource={commands.onRemoveWorkspaceSource}
    />
  );
}

export function MetadataPageContainer({
  reeDraft,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { page, focusedField } = uiChrome;
  const { locked, reeSpec } = reeDraft;
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

export function HardwareBomPageContainer({
  ree,
  reeDraft,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked } = reeDraft;
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
  const { ree, inclusionState, workspaceRemote, assemblyRun, commands } = props;
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
        inclusionState={inclusionState}
        badges={badges}
        workspaceFiles={workspaceFiles}
        workspaceSourceState={workspaceSourceState}
        artifactStatus={artifactStatus}
        evaluationState={assemblyRun.evaluationState}
        log={log}
        running={running}
        runDone={runDone}
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

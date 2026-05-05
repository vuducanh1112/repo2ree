import { PAGE } from "../../../../application/state/pages";
import { useApiRuntime } from "../../../../data/apiRuntime";
import type { SourceUploadCommit } from "../../../../domain/ree/ReeTypes";
import { useWorkflowStepPageController } from "../../hooks/useWorkflowStepPageController";
import {
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageHardwareBom,
  PageMetadataEntry,
  PageTestActivation,
  SourceAcquisitionPage,
  type WorkflowPageProps,
} from "../index";
import { type AppShellPageContainerProps, ContentSection, useWorkflowLogEntry } from "./shared";

const WORKFLOW_PAGE_COMPONENTS: Record<string, (props: WorkflowPageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

export function SourcePageContainer({
  ree,
  reeDraft,
  workspaceRemote,
  workflowRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked, repoMode } = reeDraft;
  const { badges, actionStates } = workflowRun;
  const sourceLog = useWorkflowLogEntry({
    reeId,
    runId: workflowRun.activeRunIds.source,
    fallbackTimestamp: workflowRun.timestamps.source,
  });

  if (page !== PAGE.SOURCE) {
    return null;
  }

  return (
    <SourceAcquisitionPage
      ree={ree}
      workspaceSourceState={workspaceRemote.workspaceSourceState}
      locked={locked}
      repoMode={repoMode}
      badges={badges}
      actionStates={actionStates}
      log={sourceLog}
      running={actionStates.source === "loading"}
      focusedField={focusedField}
      onReeChange={commands.setRee}
      onRepoModeChange={commands.setRepoMode}
      onGoWorkflow={commands.setPage}
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
  workflowRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { page, focusedField } = uiChrome;
  const { locked, reeSpec } = reeDraft;
  const { badges } = workflowRun;

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
      onGoWorkflow={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function HardwareBomPageContainer({
  ree,
  reeDraft,
  workflowRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked } = reeDraft;
  const { badges, actionStates, timestamps } = workflowRun;
  const hbomLog = useWorkflowLogEntry({
    reeId,
    runId: workflowRun.activeRunIds.hbom,
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
      onReeChange={commands.setRee}
      onLockedChange={commands.setLocked}
      onGoWorkflow={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onRun={commands.onRunAutomationStep}
      onCancel={commands.onCancelAction}
    />
  );
}

export function WorkflowPageContainer(props: AppShellPageContainerProps) {
  const { ree, workspaceRemote, workflowRun, commands } = props;
  const { badges } = workflowRun;
  const { workspaceFiles, workspaceSourceState, artifactStatus } = workspaceRemote;

  const workflowPageController = useWorkflowStepPageController(props);
  if (!workflowPageController) {
    return null;
  }

  const {
    workflowStep,
    log,
    running,
    runDone,
    badge,
    ts,
    missing,
    params,
    setParam,
    goToRequirements,
  } = workflowPageController;

  const WorkflowPageComponent = WORKFLOW_PAGE_COMPONENTS[workflowStep.key];
  if (!WorkflowPageComponent) {
    return null;
  }

  return (
    <ContentSection>
      <WorkflowPageComponent
        workflow={workflowStep}
        ree={ree}
        badges={badges}
        workspaceFiles={workspaceFiles}
        workspaceSourceState={workspaceSourceState}
        artifactStatus={artifactStatus}
        evaluationState={workflowRun.evaluationState}
        log={log}
        running={running}
        runDone={runDone}
        badge={badge}
        ts={ts}
        onRun={commands.onRunAutomationStep}
        onCancel={commands.onCancelAction}
        onGo={commands.setPage}
        onGoFields={goToRequirements}
        onReeChange={commands.setRee}
        onFilesChange={commands.setWorkspaceFiles}
        onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
        missing={missing}
        params={params}
        setParam={setParam}
      />
    </ContentSection>
  );
}

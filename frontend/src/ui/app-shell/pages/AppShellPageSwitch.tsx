import { type CSSProperties, type ReactNode, useMemo } from "react";
import { appShellPageForField } from "../../../application/app-shell/AppShellNavigation";
import { PAGE } from "../../../application/app-shell/AppShellPages";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useWorkflowRunLogsQuery, useWorkflowRunQuery } from "../../../data/workflow-runs/queries";
import type { LogEntry, SourceUploadCommit, WorkflowLogs } from "../../../domain/ree/ReeTypes";
import type { WorkflowRunRecord } from "../../../domain/workflow/WorkflowRun";
import type { useAppShell } from "../hooks/useAppShell";
import { useWorkflowStepPageController } from "../hooks/useWorkflowStepPageController";
import { PageArchive as ArchivePage } from "./archive/ArchivePage";
import { PageFiles as FilesPage } from "./files/FilesPage";
import {
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageHardwareBom,
  PageMetadataEntry,
  PageTestActivation,
  SourceAcquisitionPage,
  type WorkflowPageProps,
} from "./index";
import { PageOverview } from "./overview/OverviewPage";

const WORKFLOW_PAGE_COMPONENTS: Record<string, (props: WorkflowPageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

type AppShellController = ReturnType<typeof useAppShell>;

interface AppShellPageContainerProps {
  ree: AppShellController["ree"];
  reeDraft: AppShellController["reeDraft"];
  workspaceRemote: AppShellController["workspaceRemote"];
  workflowRun: AppShellController["workflowRun"];
  uiChrome: AppShellController["uiChrome"];
  level: AppShellController["level"];
  currentReeFiles: AppShellController["currentReeFiles"];
  commands: AppShellController["commands"];
}

const CONTENT_SECTION_STYLE: CSSProperties = {
  flex: 1,
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
};

function ContentSection({ children }: { children: ReactNode }) {
  return <div style={CONTENT_SECTION_STYLE}>{children}</div>;
}

function useWorkflowLogEntry(args: {
  workspaceId: string;
  runId: string | undefined;
  fallbackTimestamp?: string;
}): LogEntry | null {
  const runQuery = useWorkflowRunQuery(args.workspaceId, args.runId);
  const logsQuery = useWorkflowRunLogsQuery(args.workspaceId, args.runId);

  return useMemo(() => {
    if (!args.runId) {
      return null;
    }
    const runTimestamp = resolveWorkflowRunTimestamp(runQuery.data, args.fallbackTimestamp);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [args.fallbackTimestamp, args.runId, logsQuery.data?.lines, runQuery.data]);
}

function resolveWorkflowRunTimestamp(
  run: WorkflowRunRecord | undefined,
  fallback?: string,
): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}

export function OverviewPageContainer({
  ree,
  reeDraft,
  workspaceRemote,
  workflowRun,
  uiChrome,
  level,
  commands,
}: AppShellPageContainerProps) {
  const { page } = uiChrome;
  const { badges, timestamps } = workflowRun;
  const { workspaceFiles, sourceSnapshotFiles, artifactStatus } = workspaceRemote;
  const { locked } = reeDraft;

  if (page !== PAGE.OVERVIEW && page !== PAGE.SEAL) {
    return null;
  }

  return (
    <ContentSection>
      <PageOverview
        ree={ree}
        onReeChange={commands.setRee}
        level={level}
        onNavigate={commands.setPage}
        badges={badges}
        timestamps={timestamps}
        onGoField={(key) => {
          commands.setPage(appShellPageForField(String(key)));
          commands.setFocusedField(String(key));
        }}
        files={workspaceFiles}
        snapshotFiles={sourceSnapshotFiles}
        locked={locked}
        onSeal={commands.onSeal}
        onPreviewReviewer={commands.openReviewPreview}
        onDownloadRee={artifactStatus.sealedAt ? commands.onDownloadRee : undefined}
      />
    </ContentSection>
  );
}

export function SourcePageContainer({
  ree,
  reeDraft,
  workspaceRemote,
  workflowRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { workspaceId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked, repoMode } = reeDraft;
  const { badges, actionStates } = workflowRun;
  const sourceLog = useWorkflowLogEntry({
    workspaceId,
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
  const { workspaceId } = useApiRuntime();
  const { page, focusedField } = uiChrome;
  const { locked } = reeDraft;
  const { badges, actionStates, timestamps } = workflowRun;
  const hbomLog = useWorkflowLogEntry({
    workspaceId,
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

export function ArchivePageContainer({
  workspaceRemote,
  workflowRun,
  uiChrome,
  ree,
  commands,
}: AppShellPageContainerProps) {
  const { workspaceId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, actionStates } = workflowRun;
  const swhLog = useWorkflowLogEntry({
    workspaceId,
    runId: workflowRun.activeRunIds.swh,
    fallbackTimestamp: workflowRun.timestamps.swh,
  });
  const zenodoLog = useWorkflowLogEntry({
    workspaceId,
    runId: workflowRun.activeRunIds.zenodo,
    fallbackTimestamp: workflowRun.timestamps.zenodo,
  });
  const dataverseLog = useWorkflowLogEntry({
    workspaceId,
    runId: workflowRun.activeRunIds.dataverse,
    fallbackTimestamp: workflowRun.timestamps.dataverse,
  });
  const logs: WorkflowLogs = {};
  if (swhLog) {
    logs.swh = swhLog;
  }
  if (zenodoLog) {
    logs.zenodo = zenodoLog;
  }
  if (dataverseLog) {
    logs.dataverse = dataverseLog;
  }

  if (page !== PAGE.ARCHIVE) {
    return null;
  }

  return (
    <ContentSection>
      <ArchivePage
        ree={ree}
        artifactStatus={workspaceRemote.artifactStatus}
        badges={badges}
        logs={logs}
        actionStates={actionStates}
        onRun={commands.onRunWorkflowStep}
        onGo={commands.setPage}
      />
    </ContentSection>
  );
}

export function FilesPageContainer({
  workspaceRemote,
  uiChrome,
  currentReeFiles,
  commands,
}: AppShellPageContainerProps) {
  const { page } = uiChrome;
  const { workspaceFiles } = workspaceRemote;

  if (page !== PAGE.FILES) {
    return null;
  }

  return (
    <ContentSection>
      <FilesPage
        files={workspaceFiles}
        reeFiles={currentReeFiles}
        onDownloadWorkspaceFile={commands.onDownloadWorkspaceFile}
      />
    </ContentSection>
  );
}

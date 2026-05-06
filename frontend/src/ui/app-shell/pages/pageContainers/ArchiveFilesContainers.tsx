import { PAGE } from "../../../../application/state/pages";
import { useApiRuntime } from "../../../../data/apiRuntime";
import type { WorkflowLogs } from "../../../../domain/ree/ReeTypes";
import { PageArchive as ArchivePage } from "../archive/ArchivePage";
import { PageFiles as FilesPage } from "../files/FilesPage";
import { type AppShellPageContainerProps, ContentSection, useWorkflowLogEntry } from "./shared";

export function ArchivePageContainer({
  workspaceRemote,
  workflowRun,
  uiChrome,
  ree,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, actionStates } = workflowRun;
  const swhLog = useWorkflowLogEntry({
    reeId,
    runId: workflowRun.activeRunIds.swh,
    fallbackTimestamp: workflowRun.timestamps.swh,
  });
  const zenodoLog = useWorkflowLogEntry({
    reeId,
    runId: workflowRun.activeRunIds.zenodo,
    fallbackTimestamp: workflowRun.timestamps.zenodo,
  });
  const dataverseLog = useWorkflowLogEntry({
    reeId,
    runId: workflowRun.activeRunIds.dataverse,
    fallbackTimestamp: workflowRun.timestamps.dataverse,
  });
  const logs: WorkflowLogs = {};
  if (swhLog) logs.swh = swhLog;
  if (zenodoLog) logs.zenodo = zenodoLog;
  if (dataverseLog) logs.dataverse = dataverseLog;

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
        onRun={commands.onRunAction}
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

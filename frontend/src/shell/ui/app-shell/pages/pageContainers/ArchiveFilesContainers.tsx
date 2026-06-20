import type { ExecutionRunLogs } from "@core/ree/ReeTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { PAGE } from "../../state/pages";
import { PageArchive as ArchivePage } from "../archive/ArchivePage";
import { type AppShellPageContainerProps, ContentSection, useAssemblyRunLogEntry } from "./shared";

export function ArchivePageContainer({
  workspaceRemote,
  assemblyRun,
  uiChrome,
  ree,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, actionStates } = assemblyRun;
  const swhLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.swh,
    fallbackTimestamp: assemblyRun.timestamps.swh,
  });
  const zenodoLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.zenodo,
    fallbackTimestamp: assemblyRun.timestamps.zenodo,
  });
  const dataverseLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.dataverse,
    fallbackTimestamp: assemblyRun.timestamps.dataverse,
  });
  const logs: ExecutionRunLogs = {};
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

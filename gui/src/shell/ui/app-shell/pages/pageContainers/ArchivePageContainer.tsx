import type { ReeRunLogs } from "@core/ree/ReeTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { PAGE } from "../../state/pages";
import { PageArchive as ArchivePage } from "../archive/ArchivePage";
import { type AppShellPageContainerProps, ContentSection, useStepRunLogEntry } from "./shared";

export function ArchivePageContainer({
  workspaceRemote,
  stepRuns,
  uiChrome,
  ree,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, actionStates } = stepRuns;
  const swhLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.swh,
    fallbackTimestamp: stepRuns.timestamps.swh,
  });
  const zenodoLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.zenodo,
    fallbackTimestamp: stepRuns.timestamps.zenodo,
  });
  const dataverseLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.dataverse,
    fallbackTimestamp: stepRuns.timestamps.dataverse,
  });
  const logs: ReeRunLogs = {};
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

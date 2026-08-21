import type { ReeRunLogs } from "@core/ree/ReeTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useStepRunLogEntry } from "@shell/state/ree-editor/step-runs/useStepRunLogEntry";
import { PageArchive as ArchivePage } from "../archive/ArchivePage";
import type { ArchivePageContainerProps } from "./controllerContracts";
import { ContentSection } from "./shared";

export function ArchivePageContainer({
  workspaceRemote,
  stepRuns,
  ree,
  commands,
}: ArchivePageContainerProps) {
  const reeId = useReeId();
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

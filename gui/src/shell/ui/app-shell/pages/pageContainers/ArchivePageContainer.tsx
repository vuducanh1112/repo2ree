import type { ReeRunLogs } from "@core/ree/ReeTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useStepRunLogEntry } from "@shell/state/ree-editor/step-runs/useStepRunLogEntry";
import { lazy } from "react";
import type { ArchivePageContainerProps } from "./controllerContracts";
import { ContentSection } from "./shared";

const ArchivePage = lazy(() =>
  import("../archive/ArchivePage").then(({ PageArchive: Page }) => ({ default: Page })),
);

export function ArchivePageContainer({
  workspaceRemote,
  stepRuns,
  ree,
  commands,
}: ArchivePageContainerProps) {
  const reeId = useReeId();
  const badges = stepRuns.badges ?? {};
  const actionStates = stepRuns.actionStates ?? {};
  const activeRunIds = stepRuns.activeRunIds ?? {};
  const timestamps = stepRuns.timestamps ?? {};
  const swhLog = useStepRunLogEntry({
    reeId,
    runId: activeRunIds.swh,
    fallbackTimestamp: timestamps.swh,
  });
  const zenodoLog = useStepRunLogEntry({
    reeId,
    runId: activeRunIds.zenodo,
    fallbackTimestamp: timestamps.zenodo,
  });
  const dataverseLog = useStepRunLogEntry({
    reeId,
    runId: activeRunIds.dataverse,
    fallbackTimestamp: timestamps.dataverse,
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

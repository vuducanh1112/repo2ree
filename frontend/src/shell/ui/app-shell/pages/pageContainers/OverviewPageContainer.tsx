import { useNavigate } from "react-router-dom";
import { useApiRuntime } from "../../../../data/apiRuntime";
import { APP_ROUTE, appShellPageForField, PAGE } from "../../state/pages";
import { PageOverview } from "../overview/OverviewPage";
import { type AppShellPageContainerProps, ContentSection } from "./shared";

export function OverviewPageContainer({
  ree,
  workspaceRemote,
  assemblyRun,
  uiChrome,
  evaluation,
  commands,
  sealRunning,
  sealLog,
}: AppShellPageContainerProps) {
  const { reeId, reeApi } = useApiRuntime();
  const navigate = useNavigate();
  const { page, locked } = uiChrome;
  const { badges, timestamps } = assemblyRun;
  const { workspaceFiles, sourceSnapshotFiles, artifactStatus } = workspaceRemote;

  if (page !== PAGE.OVERVIEW && page !== PAGE.SEAL) {
    return null;
  }

  async function handleReleaseWorkbench() {
    await reeApi.deleteRee(reeId);
    navigate(APP_ROUTE.ROOT);
  }

  return (
    <ContentSection>
      <PageOverview
        ree={ree}
        onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
        onArtifactStatusChange={commands.setArtifactStatus}
        evaluation={evaluation}
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
        sealRunning={sealRunning}
        sealLog={sealLog}
        onPreviewReviewer={commands.openReviewPreview}
        onDownloadRee={artifactStatus.sealedAt ? commands.onDownloadRee : undefined}
        onReleaseWorkbench={artifactStatus.sealedAt ? handleReleaseWorkbench : undefined}
      />
    </ContentSection>
  );
}

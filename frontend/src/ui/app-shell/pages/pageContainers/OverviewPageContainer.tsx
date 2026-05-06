import { appShellPageForField, PAGE } from "../../../../shell/ui/app-shell/state/pages";
import { PageOverview } from "../overview/OverviewPage";
import { type AppShellPageContainerProps, ContentSection } from "./shared";

export function OverviewPageContainer({
  ree,
  reeDraft,
  workspaceRemote,
  assemblyRun,
  uiChrome,
  level,
  commands,
}: AppShellPageContainerProps) {
  const { page } = uiChrome;
  const { badges, timestamps } = assemblyRun;
  const { workspaceFiles, sourceSnapshotFiles, artifactStatus } = workspaceRemote;
  const { locked } = reeDraft;

  if (page !== PAGE.OVERVIEW && page !== PAGE.SEAL) {
    return null;
  }

  return (
    <ContentSection>
      <PageOverview
        ree={ree}
        onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
        onArtifactStatusChange={commands.setArtifactStatus}
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

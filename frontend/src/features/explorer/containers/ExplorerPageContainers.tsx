import type { CSSProperties, ReactNode } from "react";
import { PAGE } from "../../../constants/pages";
import type { SourceUploadCommit } from "../../../types";
import { PageArchive as ArchivePage } from "../../archive/PageArchive";
import { PageFiles as FilesPage } from "../../files/PageFiles";
import { PageOverview } from "../../overview/PageOverview";
import type { useExplorerController } from "../hooks/useExplorerController";
import { useServicePageController } from "../hooks/useServicePageController";
import {
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageMetadataEntry,
  PageSourceRepoEntry,
  PageTestActivation,
  type ServicePageProps,
} from "../screens";
import { explorerPageForField } from "../utils/navigation";

const SERVICE_PAGE_COMPONENTS: Record<string, (props: ServicePageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

type ExplorerController = ReturnType<typeof useExplorerController>;

export interface ExplorerPageContainerProps {
  state: ExplorerController["state"];
  commands: ExplorerController["commands"];
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

export function OverviewPageContainer({ state, commands }: ExplorerPageContainerProps) {
  const {
    page,
    ree,
    level,
    badges,
    timestamps,
    virtualFiles,
    immutableSourceSnapshotFiles,
    locked,
  } = state;

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
          commands.setPage(explorerPageForField(String(key)));
          commands.setFocusedField(String(key));
        }}
        files={virtualFiles}
        snapshotFiles={immutableSourceSnapshotFiles}
        locked={locked}
        onSeal={commands.onSeal}
        onPreviewReviewer={commands.openReviewerPreview}
        onDownloadRee={ree._sealedAt ? commands.onDownloadRee : undefined}
      />
    </ContentSection>
  );
}

export function SourcePageContainer({ state, commands }: ExplorerPageContainerProps) {
  const { page, ree, locked, repoMode, badges, actionStates, focusedField } = state;

  if (page !== PAGE.SOURCE) {
    return null;
  }

  return (
    <PageSourceRepoEntry
      ree={ree}
      locked={locked}
      repoMode={repoMode}
      badges={badges}
      actionStates={actionStates}
      focusedField={focusedField}
      onReeChange={commands.setRee}
      onRepoModeChange={commands.setRepoMode}
      onGoService={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onDownloadSource={commands.onDownloadSourceFiles}
      onCancelSource={() => commands.onCancelAction("source")}
      onWorkspaceUpload={(payload: SourceUploadCommit) => commands.onWorkspaceUpload(payload)}
      onRemoveWorkspaceSource={commands.onRemoveWorkspaceSource}
    />
  );
}

export function MetadataPageContainer({ state, commands }: ExplorerPageContainerProps) {
  const { page, ree, locked, badges, focusedField } = state;

  if (page !== PAGE.METADATA) {
    return null;
  }

  return (
    <PageMetadataEntry
      ree={ree}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      onReeChange={commands.setRee}
      onLockedChange={commands.setLocked}
      onGoService={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function ServicePageContainer({ state, commands }: ExplorerPageContainerProps) {
  const { ree, badges, virtualFiles } = state;

  const serviceController = useServicePageController({ state, commands });
  if (!serviceController) {
    return null;
  }

  const { service, log, running, runDone, badge, ts, missing, params, setParam, goToRequirements } =
    serviceController;

  const ServicePageComponent = SERVICE_PAGE_COMPONENTS[service.key];
  if (!ServicePageComponent) {
    return null;
  }

  return (
    <ContentSection>
      <ServicePageComponent
        svc={service}
        ree={ree}
        badges={badges}
        virtualFiles={virtualFiles}
        log={log}
        running={running}
        runDone={runDone}
        badge={badge}
        ts={ts}
        onRun={commands.onRunWorkflowAction}
        onCancel={commands.onCancelAction}
        onGo={commands.setPage}
        onGoFields={goToRequirements}
        onReeChange={commands.setRee}
        onFilesChange={commands.setVirtualFiles}
        onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
        missing={missing}
        params={params}
        setParam={setParam}
      />
    </ContentSection>
  );
}

export function ArchivePageContainer({ state, commands }: ExplorerPageContainerProps) {
  const { page, ree, badges, serviceLogs, actionStates } = state;

  if (page !== PAGE.ARCHIVE) {
    return null;
  }

  return (
    <ContentSection>
      <ArchivePage
        ree={ree}
        badges={badges}
        logs={serviceLogs}
        actionStates={actionStates}
        onRun={commands.onRunAction}
        onGo={commands.setPage}
      />
    </ContentSection>
  );
}

export function FilesPageContainer({ state, commands }: ExplorerPageContainerProps) {
  const { page, virtualFiles, currentReeFiles } = state;

  if (page !== PAGE.FILES) {
    return null;
  }

  return (
    <ContentSection>
      <FilesPage
        files={virtualFiles}
        reeFiles={currentReeFiles}
        onDownloadWorkspaceFile={commands.onDownloadWorkspaceFile}
      />
    </ContentSection>
  );
}

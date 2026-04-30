import type { CSSProperties, ReactNode } from "react";
import { workspaceShellPageForField } from "../../../application/workspace-shell/WorkspaceShellNavigation";
import { PAGE } from "../../../application/workspace-shell/WorkspaceShellPages";
import type { SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import { useWorkflowStepPageController } from "../hooks/useWorkflowStepPageController";
import type { useWorkspaceShell } from "../hooks/useWorkspaceShell";
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

type WorkspaceShellController = ReturnType<typeof useWorkspaceShell>;

interface WorkspaceShellPageContainerProps {
  state: WorkspaceShellController["state"];
  commands: WorkspaceShellController["commands"];
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

export function OverviewPageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { page, ree, level, badges, timestamps, workspaceFiles, sourceSnapshotFiles, locked } =
    state;

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
          commands.setPage(workspaceShellPageForField(String(key)));
          commands.setFocusedField(String(key));
        }}
        files={workspaceFiles}
        snapshotFiles={sourceSnapshotFiles}
        locked={locked}
        onSeal={commands.onSeal}
        onPreviewReviewer={commands.openReviewPreview}
        onDownloadRee={ree._sealedAt ? commands.onDownloadRee : undefined}
      />
    </ContentSection>
  );
}

export function SourcePageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { page, ree, locked, repoMode, badges, actionStates, focusedField, workflowLogs } = state;

  if (page !== PAGE.SOURCE) {
    return null;
  }

  return (
    <SourceAcquisitionPage
      ree={ree}
      locked={locked}
      repoMode={repoMode}
      badges={badges}
      actionStates={actionStates}
      log={workflowLogs.source || null}
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

export function MetadataPageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
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
      onGoWorkflow={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function HardwareBomPageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { page, ree, locked, badges, focusedField, workflowLogs, actionStates, timestamps } = state;

  if (page !== PAGE.HBOM) {
    return null;
  }

  return (
    <PageHardwareBom
      ree={ree}
      locked={locked}
      badges={badges}
      log={workflowLogs.hbom || null}
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

export function WorkflowPageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { ree, badges, workspaceFiles } = state;

  const workflowPageController = useWorkflowStepPageController({ state, commands });
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

export function ArchivePageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { page, ree, badges, workflowLogs, actionStates } = state;

  if (page !== PAGE.ARCHIVE) {
    return null;
  }

  return (
    <ContentSection>
      <ArchivePage
        ree={ree}
        badges={badges}
        logs={workflowLogs}
        actionStates={actionStates}
        onRun={commands.onRunWorkflowStep}
        onGo={commands.setPage}
      />
    </ContentSection>
  );
}

export function FilesPageContainer({ state, commands }: WorkspaceShellPageContainerProps) {
  const { page, workspaceFiles, currentReeFiles } = state;

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

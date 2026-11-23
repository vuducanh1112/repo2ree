import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { activeNode, CANVAS_NODES, isNodeStale } from "@core/canvas/canvasNodes";
import type { ReviewStepKey } from "@core/generated/vocabulary";
import { useWorkspaceNavigationGuard } from "@shell/state/ree-editor/workspace-sync/useWorkspaceNavigationGuard";
import { useCallback, useMemo, useState } from "react";
import { WorkspaceLoadErrorView, WorkspaceLoadingView } from "../errors/WorkspaceLoadView";
import { BuildBadge } from "../shared/components/BuildBadge";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { AppShellContent } from "./AppShellContent";
import styles from "./AppShellView.module.css";
import { authoringWorkflowModel } from "./canvas/AuthoringConsole";
import { CanvasHub } from "./canvas/CanvasHub";
import { RunHud } from "./canvas/RunHud";
import { ReviewEvidence } from "./canvas/review/ReviewEvidence";
import { useReviewWorkflowModel } from "./canvas/review/useReviewWorkflowModel";
import { SealContent } from "./canvas/SealContent";
import { SourceAcquisitionContent } from "./canvas/SourceAcquisitionContent";
import { WorkspaceDrawer } from "./canvas/WorkspaceDrawer";
import { EnvironmentBuild } from "./components/EnvironmentBuild";
import { ReeSyncStatus } from "./components/ReeSyncStatus";
import { WorkspaceFooterBar } from "./components/WorkspaceFooterBar";
import { type WorkflowMode, WorkspaceStatusBar } from "./components/WorkspaceStatusBar";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";

interface AppShellViewProps {
  onBack: () => void;
}

const WINDOW_TITLE: Partial<Record<AppShellPage, string>> = {
  [PAGE.ACQUIRE_SOURCE]: "Source Acquisition",
};

const drawerTitle = (page: AppShellPage) => WINDOW_TITLE[page];

export function AppShellView({ onBack }: AppShellViewProps) {
  return (
    <AppShellProvider>
      <AppShellViewInner onBack={onBack} />
    </AppShellProvider>
  );
}

function AppShellViewInner({ onBack }: AppShellViewProps) {
  const {
    model: {
      provisioned,
      reeIntent,
      ree,
      workspaceRemote,
      stepRuns,
      evaluation,
      currentReeFiles,
      authorReceipts,
    },
    chrome: uiChrome,
    sync: {
      workspaceHydration,
      retryWorkspaceHydration,
      reeIntentSyncState,
      isReeIntentDirty,
      retryReeIntentSync,
    },
    commands,
    seal: { running: sealRunning, log: sealLog },
  } = useAppShell();
  const { badges } = stepRuns;
  const { toast } = uiChrome;
  const page = uiChrome.page;
  const authoring = authoringWorkflowModel(ree);
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>("authoring");
  const [reviewStep, setReviewStep] = useState<ReviewStepKey | null>(null);
  const review = useReviewWorkflowModel({
    experiments: ree.spec.experiments ?? [],
    active: provisioned && workflowMode === "review",
  });
  const staleNodeKeys = useMemo(
    () => new Set(CANVAS_NODES.filter((node) => isNodeStale(node, ree)).map((node) => node.key)),
    [ree],
  );
  useWorkspaceNavigationGuard({
    shouldBlock: isReeIntentDirty,
    flush: commands.flushReeIntent,
    onFlushFailed: () =>
      commands.showToast("Left with unsaved changes — the last save did not go through", "error"),
  });
  const openPage = useCallback(
    (next: typeof page) => {
      commands.setPage(next);
      if (next !== PAGE.CANVAS) commands.setReceiptsConsoleOpen(false);
      setReviewStep(null);
    },
    [commands],
  );

  const openReviewStep = useCallback(
    (step: ReviewStepKey) => {
      setReviewStep(step);
      commands.setPage(PAGE.CANVAS);
    },
    [commands],
  );

  const changeWorkflowMode = useCallback((next: WorkflowMode) => {
    setWorkflowMode(next);
    if (next === "authoring") setReviewStep(null);
  }, []);

  const drawerOpen = provisioned && page !== PAGE.CANVAS;
  const drawerBody = useMemo(() => {
    if (!drawerOpen) return null;
    if (page === PAGE.ACQUIRE_SOURCE) {
      return (
        <SourceAcquisitionContent
          ree={ree}
          workspaceRemote={workspaceRemote}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          commands={commands}
        />
      );
    }
    if (page === PAGE.SEAL_REE) {
      return (
        <SealContent
          ree={ree}
          badges={badges}
          locked={uiChrome.locked}
          sealRunning={sealRunning}
          sealLog={sealLog}
          onSeal={commands.onSeal}
        />
      );
    }
    return (
      <AppShellContent
        page={page}
        ree={ree}
        reeIntent={reeIntent}
        workspaceRemote={workspaceRemote}
        stepRuns={stepRuns}
        uiChrome={uiChrome}
        currentReeFiles={currentReeFiles}
        commands={commands}
      />
    );
  }, [
    drawerOpen,
    page,
    uiChrome,
    ree,
    reeIntent,
    workspaceRemote,
    stepRuns,
    currentReeFiles,
    commands,
    sealRunning,
    sealLog,
    badges,
  ]);

  if (provisioned && workspaceHydration.status === "loading") {
    return <WorkspaceLoadingView onBack={onBack} />;
  }

  if (provisioned && workspaceHydration.status === "error") {
    return (
      <WorkspaceLoadErrorView
        error={workspaceHydration.error}
        onRetry={retryWorkspaceHydration}
        onBack={onBack}
      />
    );
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <button type="button" onClick={onBack} className={styles.back}>
          {Ic.arrowLeft()}
          <span>back</span>
        </button>
        <div aria-hidden className={styles.rule} />
        <span aria-hidden className={styles.mark}>
          {Ic.layers()}
        </span>
        <span className={styles.product}>REE Editor</span>
        <BuildBadge />
        <span aria-hidden className={styles.separator}>
          /
        </span>
        <span className={styles.reeName}>{ree.spec.name || "untitled"}</span>
        {provisioned && (
          <ReeSyncStatus state={reeIntentSyncState} onRetry={() => void retryReeIntentSync()} />
        )}
        <div className={styles.spacer} />
        {provisioned && <EnvironmentBuild />}
        <button
          type="button"
          onClick={commands.onDownloadRee}
          disabled={!provisioned}
          className={styles.download}
        >
          <span aria-hidden className={styles.downloadIcon}>
            {Ic.download(13)}
          </span>
          <span className={styles.downloadLabel}>Download REE</span>
        </button>
      </header>

      {provisioned && (
        <WorkspaceStatusBar
          page={page}
          authoring={authoring}
          review={review}
          mode={workflowMode}
          onModeChange={changeWorkflowMode}
          openReviewStep={reviewStep}
          onOpenReviewStep={openReviewStep}
          workspaceFiles={workspaceRemote.workspaceFiles}
          reeFiles={currentReeFiles}
          receiptCount={authorReceipts.length}
          filesOpen={uiChrome.filesConsoleOpen}
          receiptsOpen={uiChrome.receiptsConsoleOpen}
          onNavigate={openPage}
          onFilesOpenChange={commands.setFilesConsoleOpen}
          onReceiptsOpenChange={commands.setReceiptsConsoleOpen}
        />
      )}

      <main className={styles.stage}>
        {provisioned && (
          <>
            <div className={styles.canvasPane}>
              <CanvasHub
                page={page}
                ree={ree}
                evaluation={evaluation}
                badges={badges}
                nextPage={authoring.nextPage}
                blockedNodeKeys={
                  new Set(
                    Object.entries(authoring.statuses)
                      .filter(([, status]) => status === "blocked")
                      .map(([key]) => key),
                  )
                }
                sealRunning={sealRunning}
                provisioned={provisioned}
                staleNodeKeys={staleNodeKeys}
                onNavigate={openPage}
                workspaceFiles={workspaceRemote.workspaceFiles}
                reeFiles={currentReeFiles}
                sourceRepo={workspaceRemote.sourceRepo}
                authorReceipts={authorReceipts}
                filesConsoleOpen={uiChrome.filesConsoleOpen}
                onFilesConsoleOpenChange={commands.setFilesConsoleOpen}
                receiptsConsoleOpen={uiChrome.receiptsConsoleOpen}
                onReceiptsConsoleOpenChange={commands.setReceiptsConsoleOpen}
                benchConsoleOpen={uiChrome.benchConsoleOpen}
                onBenchConsoleOpenChange={commands.setBenchConsoleOpen}
              />

              <RunHud
                open={uiChrome.logsConsoleOpen}
                onOpenChange={commands.setLogsConsoleOpen}
                externallyTriggered
              />
            </div>

            {drawerOpen && (
              <WorkspaceDrawer
                node={activeNode(page)}
                title={drawerTitle(page)}
                onClose={() => commands.setPage(PAGE.CANVAS)}
              >
                {drawerBody}
              </WorkspaceDrawer>
            )}

            {!drawerOpen && reviewStep && (
              <WorkspaceDrawer
                node={undefined}
                title="Review evidence"
                subtitle="Review"
                icon={Ic.shield(13)}
                onClose={() => setReviewStep(null)}
              >
                <ReviewEvidence model={review} focusStep={reviewStep} />
              </WorkspaceDrawer>
            )}
          </>
        )}
      </main>

      {provisioned && (
        <WorkspaceFooterBar
          provisioned={provisioned}
          benchOpen={uiChrome.benchConsoleOpen}
          logsOpen={uiChrome.logsConsoleOpen}
          onBenchOpenChange={commands.setBenchConsoleOpen}
          onLogsOpenChange={commands.setLogsConsoleOpen}
        />
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={commands.clearToast} />}
    </div>
  );
}

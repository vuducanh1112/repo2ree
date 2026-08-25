import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { useWorkspaceNavigationGuard } from "@shell/state/ree-editor/workspace-sync/useWorkspaceNavigationGuard";
import { useCallback, useMemo } from "react";
import { WorkspaceLoadErrorView, WorkspaceLoadingView } from "../errors/WorkspaceLoadView";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { AppShellContent } from "./AppShellContent";
import styles from "./AppShellView.module.css";
import { useAuthoringWorkflowModel } from "./canvas/AuthoringConsole";
import { CanvasHub } from "./canvas/CanvasHub";
import { RunHud } from "./canvas/RunHud";
import { SealContent } from "./canvas/SealContent";
import { SourceAcquisitionContent } from "./canvas/SourceAcquisitionContent";
import { WorkbenchLab } from "./canvas/WorkbenchLab";
import { ReeSyncStatus } from "./components/ReeSyncStatus";
import { WorkspaceFooterBar } from "./components/WorkspaceFooterBar";
import { WorkspaceStatusBar } from "./components/WorkspaceStatusBar";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";

interface AppShellViewProps {
  onBack: () => void;
}

const NO_STALE_NODE_KEYS = new Set<string>();

// Pages whose canvas node carries a compact label; the window says the longer
// name. Everything else takes its node's own label.
const WINDOW_TITLE: Partial<Record<AppShellPage, string>> = {
  [PAGE.SOURCE]: "Source Acquisition",
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
  // Derived once here so the status-bar DAG and the canvas panels name the
  // same next step; deriving it twice lets the two drift apart.
  const authoring = useAuthoringWorkflowModel(ree, badges);
  useWorkspaceNavigationGuard({
    shouldBlock: isReeIntentDirty,
    flush: commands.flushReeIntent,
  });
  // The constellation (pod hub) is the home view and stays live: pages open as
  // windows standing on it beside their own node, several at once, so moving
  // between steps is panning rather than replacing what is on screen.
  const openPage = useCallback(
    (next: typeof page) => {
      commands.setPage(next);
      if (next !== PAGE.CANVAS) commands.setReceiptsConsoleOpen(false);
    },
    [commands],
  );

  // Each open window's body, memoised per page. CanvasHub re-renders on every
  // frame of a pan to follow its node; a stable element per page is what keeps
  // that from reconciling the page underneath it sixty times a second.
  const pageBodies = useMemo(() => {
    const body = (target: typeof page) => {
      if (target === PAGE.SOURCE) {
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
      if (target === PAGE.SEAL) {
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
          page={target}
          ree={ree}
          reeIntent={reeIntent}
          workspaceRemote={workspaceRemote}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          currentReeFiles={currentReeFiles}
          commands={commands}
        />
      );
    };
    return new Map(uiChrome.openPages.map(({ page: open }) => [open, body(open)] as const));
  }, [
    uiChrome,
    ree,
    reeIntent,
    workspaceRemote,
    stepRuns,
    currentReeFiles,
    commands,
    badges,
    sealRunning,
    sealLog,
  ]);

  const renderPage = useCallback(
    (target: typeof page) => pageBodies.get(target) ?? null,
    [pageBodies],
  );

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
        <span aria-hidden className={styles.separator}>
          /
        </span>
        <span className={styles.reeName}>{ree.spec.name || "untitled"}</span>
        {provisioned && (
          <ReeSyncStatus state={reeIntentSyncState} onRetry={() => void retryReeIntentSync()} />
        )}
        <div className={styles.spacer} />
        <button
          type="button"
          onClick={commands.onDownloadRee}
          disabled={!workspaceRemote.artifactStatus.sealedAt}
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
          experiments={ree.spec.experiments ?? []}
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
        {!provisioned ? (
          // First screen of REE creation: the workbench IS the canvas — the lab
          // the dormant pod sits in. Configuring it powers the lab on.
          <WorkbenchLab evaluation={evaluation} />
        ) : (
          <CanvasHub
            page={page}
            ree={ree}
            evaluation={evaluation}
            badges={badges}
            nextPage={authoring.nextPage}
            staleNodeKeys={NO_STALE_NODE_KEYS}
            provisioned={provisioned}
            openPages={uiChrome.openPages}
            renderPage={renderPage}
            onClosePage={commands.closePage}
            onPositionPage={commands.setPageWindowPosition}
            onSizePage={commands.setPageWindowSize}
            pageTitle={drawerTitle}
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
        )}

        {/* Cross-page logs console: every run of this REE, split by step. */}
        {provisioned && (
          <RunHud
            open={uiChrome.logsConsoleOpen}
            onOpenChange={commands.setLogsConsoleOpen}
            externallyTriggered
          />
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

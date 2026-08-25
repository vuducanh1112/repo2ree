import { PAGE } from "@core/app-shell/pages";
import { activeNode } from "@core/canvas/canvasNodes";
import { useWorkspaceNavigationGuard } from "@shell/state/ree-editor/workspace-sync/useWorkspaceNavigationGuard";
import { useCallback } from "react";
import { WorkspaceLoadErrorView, WorkspaceLoadingView } from "../errors/WorkspaceLoadView";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { AppShellContent } from "./AppShellContent";
import styles from "./AppShellView.module.css";
import { CanvasHub } from "./canvas/CanvasHub";
import { RunHud } from "./canvas/RunHud";
import { SealContent } from "./canvas/SealContent";
import { SourceAcquisitionContent } from "./canvas/SourceAcquisitionContent";
import { WorkbenchLab } from "./canvas/WorkbenchLab";
import { WorkspaceDrawer } from "./canvas/WorkspaceDrawer";
import { ReeSyncStatus } from "./components/ReeSyncStatus";
import { WorkspaceStatusBar } from "./components/WorkspaceStatusBar";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";

interface AppShellViewProps {
  onBack: () => void;
}

const NO_STALE_NODE_KEYS = new Set<string>();

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
  useWorkspaceNavigationGuard({
    shouldBlock: isReeIntentDirty,
    flush: commands.flushReeIntent,
  });
  // The constellation (pod hub) is the home view. Every workflow page opens in
  // the same resizable drawer so moving between steps never changes navigation
  // or spatial context.
  const drawerOpen = page !== PAGE.CANVAS;
  const sealOpen = page === PAGE.SEAL;
  const sourceOpen = page === PAGE.SOURCE;
  const openPage = useCallback(
    (next: typeof page) => {
      commands.setPage(next);
      if (next !== PAGE.CANVAS) commands.setReceiptsConsoleOpen(false);
    },
    [commands],
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
          ree={ree}
          badges={badges}
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
            staleNodeKeys={NO_STALE_NODE_KEYS}
            provisioned={provisioned}
            dimmed={false}
            onNavigate={openPage}
            workspaceFiles={workspaceRemote.workspaceFiles}
            reeFiles={currentReeFiles}
            sourceRepo={workspaceRemote.sourceRepo}
            authorReceipts={authorReceipts}
            filesConsoleOpen={uiChrome.filesConsoleOpen}
            onFilesConsoleOpenChange={commands.setFilesConsoleOpen}
            receiptsConsoleOpen={uiChrome.receiptsConsoleOpen}
            onReceiptsConsoleOpenChange={commands.setReceiptsConsoleOpen}
          />
        )}

        {provisioned && drawerOpen && (
          <WorkspaceDrawer
            node={activeNode(page)}
            title={sourceOpen ? "Source Acquisition" : undefined}
            onClose={() => commands.setPage(PAGE.CANVAS)}
          >
            {sourceOpen ? (
              <SourceAcquisitionContent
                ree={ree}
                workspaceRemote={workspaceRemote}
                stepRuns={stepRuns}
                uiChrome={uiChrome}
                commands={commands}
              />
            ) : sealOpen ? (
              <SealContent
                ree={ree}
                badges={badges}
                locked={uiChrome.locked}
                sealRunning={sealRunning}
                sealLog={sealLog}
                onSeal={commands.onSeal}
              />
            ) : (
              <AppShellContent
                ree={ree}
                reeIntent={reeIntent}
                workspaceRemote={workspaceRemote}
                stepRuns={stepRuns}
                uiChrome={uiChrome}
                currentReeFiles={currentReeFiles}
                commands={commands}
              />
            )}
          </WorkspaceDrawer>
        )}

        {/* Cross-page logs console: every run of this REE, split by step. */}
        {provisioned && <RunHud />}
      </main>

      {toast && <Toast message={toast.message} type={toast.type} onClose={commands.clearToast} />}
    </div>
  );
}

import { PAGE } from "@core/app-shell/pages";
import { activeNode } from "@core/canvas/canvasNodes";
import { addExperiment } from "@core/ree/experimentOps";
import { useState } from "react";
import { WorkspaceLoadErrorView, WorkspaceLoadingView } from "../errors/WorkspaceLoadView";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { AppShellContent } from "./AppShellContent";
import styles from "./AppShellView.module.css";
import { CanvasHub } from "./canvas/CanvasHub";
import { FocusDock } from "./canvas/FocusDock";
import { RunHud } from "./canvas/RunHud";
import { SealHubPanel } from "./canvas/SealHubPanel";
import { SourceHubPanel } from "./canvas/SourceHubPanel";
import { WorkbenchLab } from "./canvas/WorkbenchLab";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";

interface AppShellViewProps {
  onBack: () => void;
}

export function AppShellView({ onBack }: AppShellViewProps) {
  return (
    <AppShellProvider>
      <AppShellViewInner onBack={onBack} />
    </AppShellProvider>
  );
}

function AppShellViewInner({ onBack }: AppShellViewProps) {
  const {
    provisioned,
    workspaceHydration,
    retryWorkspaceHydration,
    reeIntent,
    ree,
    workspaceRemote,
    stepRuns,
    uiChrome,
    evaluation,
    currentReeFiles,
    commands,
    sealRunning,
    sealLog,
  } = useAppShell();
  const { badges } = stepRuns;
  const { toast } = uiChrome;
  const page = uiChrome.page;
  // The constellation (pod hub) is the home view. Seal and source acquisition
  // live inside the hub as compact floating panels; every other page docks
  // beside the pod.
  const sealOpen = page === PAGE.SEAL;
  const sourceOpen = page === PAGE.SOURCE;
  const dockOpen = page !== PAGE.CANVAS && !sealOpen && !sourceOpen;

  // Screen rect of the canvas panel that opened the dock, so the edit view can
  // grow out of the panel the user clicked instead of feeling like a new page.
  const [originRect, setOriginRect] = useState<DOMRect | null>(null);
  const openPage = (next: typeof page, rect?: DOMRect) => {
    if (rect) setOriginRect(rect);
    commands.setPage(next);
  };

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
        <span className={styles.reeName}>{ree.name || "untitled"}</span>
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
          Download REE
        </button>
      </header>

      <div className={styles.stage}>
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
            staleNodeKeys={new Set<string>()}
            provisioned={provisioned}
            dimmed={dockOpen}
            onNavigate={openPage}
            onAddExperiment={() => commands.setReeSpec(addExperiment)}
            onOpenExperimentsOverview={() => {
              commands.setFocusedField(null);
              openPage(PAGE.EXPERIMENTS);
            }}
            onOpenExperiment={(index) => {
              commands.setFocusedField(`experiments[${index}].name`);
              openPage(PAGE.EXPERIMENTS);
            }}
            onOpenRuntime={() => {
              commands.setFocusedField(null);
              openPage(PAGE.BUILD);
            }}
            workspaceFiles={workspaceRemote.workspaceFiles}
            reeFiles={currentReeFiles}
            sourceRepo={workspaceRemote.sourceRepo}
            filesConsoleOpen={uiChrome.filesConsoleOpen}
            onFilesConsoleOpenChange={commands.setFilesConsoleOpen}
          />
        )}

        {provisioned && dockOpen && (
          <FocusDock
            node={activeNode(page)}
            originRect={originRect}
            closable={provisioned}
            onClose={() => commands.setPage(PAGE.CANVAS)}
          >
            <AppShellContent
              ree={ree}
              reeIntent={reeIntent}
              workspaceRemote={workspaceRemote}
              stepRuns={stepRuns}
              uiChrome={uiChrome}
              evaluation={evaluation}
              currentReeFiles={currentReeFiles}
              commands={commands}
              sealRunning={sealRunning}
              sealLog={sealLog}
            />
          </FocusDock>
        )}

        {sourceOpen && (
          <SourceHubPanel
            ree={ree}
            workspaceRemote={workspaceRemote}
            stepRuns={stepRuns}
            uiChrome={uiChrome}
            commands={commands}
            onClose={() => commands.setPage(PAGE.CANVAS)}
          />
        )}

        {/* Cross-page logs console: every run of this REE, split by step. */}
        {provisioned && <RunHud />}

        {sealOpen && (
          <SealHubPanel
            ree={ree}
            badges={badges}
            locked={uiChrome.locked}
            sealRunning={sealRunning}
            sealLog={sealLog}
            onSeal={commands.onSeal}
            onClose={() => commands.setPage(PAGE.CANVAS)}
          />
        )}
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={commands.clearToast} />}
    </div>
  );
}

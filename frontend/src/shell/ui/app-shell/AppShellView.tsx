import { addExperiment } from "@core/ree/experimentOps";
import { useState } from "react";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { C, F, hoverBg, hoverColor } from "../theme/theme";
import { AppShellContent } from "./AppShellContent";
import { CanvasHub } from "./canvas/CanvasHub";
import { activeNode } from "./canvas/canvasNodes";
import { FocusDock } from "./canvas/FocusDock";
import { SbomHubPanel } from "./canvas/SbomHubPanel";
import { SealHubPanel } from "./canvas/SealHubPanel";
import { SourceHubPanel } from "./canvas/SourceHubPanel";
import { WorkbenchLab } from "./canvas/WorkbenchLab";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";
import { PAGE } from "./state/pages";

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
    reeIntent,
    ree,
    workspaceRemote,
    assemblyRun,
    uiChrome,
    evaluation,
    currentReeFiles,
    commands,
    sealRunning,
    sealLog,
  } = useAppShell();
  const { badges } = assemblyRun;
  const { toast } = uiChrome;
  const page = uiChrome.page;
  // The constellation (pod hub) is the home view. Seal and the one-press SBOM
  // step live inside the hub as compact floating panels; every other page docks
  // beside the pod.
  const sealOpen = page === PAGE.SEAL;
  const sbomOpen = page === PAGE.SBOM;
  const sourceOpen = page === PAGE.SOURCE;
  const dockOpen = page !== PAGE.OVERVIEW && !sealOpen && !sbomOpen && !sourceOpen;

  // Screen rect of the canvas panel that opened the dock, so the edit view can
  // grow out of the panel the user clicked instead of feeling like a new page.
  const [originRect, setOriginRect] = useState<DOMRect | null>(null);
  const openPage = (next: typeof page, rect?: DOMRect) => {
    if (rect) setOriginRect(rect);
    commands.setPage(next);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          {...hoverColor(C.textMid, C.textMuted)}
          {...hoverBg(C.surfaceAlt, "transparent")}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Editor
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={commands.onDownloadRee}
          disabled={!workspaceRemote.artifactStatus.sealedAt}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "rgba(220, 252, 231, 0.7)",
            border: "1px solid rgba(34, 197, 94, 0.42)",
            borderRadius: 7,
            cursor: workspaceRemote.artifactStatus.sealedAt ? "pointer" : "not-allowed",
            color: "#15803d",
            padding: "5px 11px",
            fontSize: 12.5,
            fontWeight: 600,
            fontFamily: F.sans,
            transition: "all 0.12s",
            opacity: workspaceRemote.artifactStatus.sealedAt ? 1 : 0.4,
          }}
          {...(workspaceRemote.artifactStatus.sealedAt
            ? hoverBg("rgba(220, 252, 231, 0.9)", "rgba(220, 252, 231, 0.7)")
            : {})}
        >
          <span style={{ display: "flex" }}>{Ic.download(13)}</span>
          Download REE
        </button>
      </header>

      <div style={{ flex: 1, position: "relative", overflow: "hidden", minHeight: 0 }}>
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
            reeFiles={currentReeFiles}
            draftManifest={workspaceRemote.draftManifest}
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
            onClose={() => commands.setPage(PAGE.OVERVIEW)}
          >
            <AppShellContent
              ree={ree}
              reeIntent={reeIntent}
              workspaceRemote={workspaceRemote}
              assemblyRun={assemblyRun}
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
            assemblyRun={assemblyRun}
            uiChrome={uiChrome}
            commands={commands}
            onClose={() => commands.setPage(PAGE.OVERVIEW)}
          />
        )}

        {sbomOpen && (
          <SbomHubPanel
            ree={ree}
            workspaceRemote={workspaceRemote}
            assemblyRun={assemblyRun}
            uiChrome={uiChrome}
            commands={commands}
            onClose={() => commands.setPage(PAGE.OVERVIEW)}
          />
        )}

        {sealOpen && (
          <SealHubPanel
            ree={ree}
            evaluation={evaluation}
            badges={badges}
            locked={uiChrome.locked}
            sealRunning={sealRunning}
            sealLog={sealLog}
            onSeal={commands.onSeal}
            onClose={() => commands.setPage(PAGE.OVERVIEW)}
          />
        )}
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={commands.clearToast} />}
    </div>
  );
}

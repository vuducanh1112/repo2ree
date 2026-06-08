import type React from "react";
import type { StepState } from "../../../core/ree-assembly/assemblyStepTypes";
import type { StandingMeta } from "../../../core/review/axes";
import type { EvaluationState } from "../../../core/review/EvaluationState";
import { Ic } from "../shared/components/Icon";
import { Toast } from "../shared/components/Toast";
import { C, F, hoverBg, hoverColor } from "../theme/theme";
import { AppShellContent } from "./AppShellContent";
import { AppShellSidebar } from "./AppShellSidebar";
import { ReviewerPreviewOverlay } from "./components/ReviewerPreviewOverlay";
import { useAppShell } from "./hooks/useAppShell";
import { AppShellProvider } from "./providers/AppShellProvider";
import { PAGE } from "./state/pages";

interface AppShellViewProps {
  onBack: () => void;
  PodOrbitControl: React.ComponentType<{
    evaluation: EvaluationState;
    levelMeta: StandingMeta;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

export function AppShellView({ onBack, PodOrbitControl }: AppShellViewProps) {
  return (
    <AppShellProvider>
      <AppShellViewInner onBack={onBack} PodOrbitControl={PodOrbitControl} />
    </AppShellProvider>
  );
}

function AppShellViewInner({ onBack, PodOrbitControl }: AppShellViewProps) {
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
    reviewer,
    sealRunning,
    sealLog,
  } = useAppShell();
  const { badges, timestamps } = assemblyRun;
  const { toast, navCollapsed } = uiChrome;
  const page = !provisioned ? PAGE.WORKBENCH : uiChrome.page;
  const effectiveUiChrome = provisioned ? uiChrome : { ...uiChrome, page };

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
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        <AppShellSidebar
          page={page}
          ree={ree}
          navCollapsed={navCollapsed}
          badges={badges}
          timestamps={timestamps}
          provisioned={provisioned}
          setPage={commands.setPage}
          setNavCollapsed={commands.setNavCollapsed}
          onPreviewReviewer={commands.openReviewPreview}
        />

        <AppShellContent
          ree={ree}
          reeIntent={reeIntent}
          workspaceRemote={workspaceRemote}
          assemblyRun={assemblyRun}
          uiChrome={effectiveUiChrome}
          evaluation={evaluation}
          currentReeFiles={currentReeFiles}
          commands={commands}
          sealRunning={sealRunning}
          sealLog={sealLog}
        />
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={commands.clearToast} />}

      <ReviewerPreviewOverlay
        open={reviewer.showReviewPreview}
        ree={ree}
        onClose={commands.closeReviewPreview}
        PodOrbitControl={PodOrbitControl}
      />
    </div>
  );
}

import type React from "react";
import { useMemo } from "react";
import { Ic } from "../../components/Icon";
import { Toast } from "../../components/Toast";
import { C, F, hoverBg, hoverColor } from "../../constants/theme";
import { explorerActions, explorerSelectors, useAppContext } from "../../context";
import type { ExplorerPage, FileTreeNode, Ree, ServiceParams } from "../../types";
import { buildCurrentReeArchiveEntries, reeArchiveEntriesToFiles } from "../../utils";
import { ExplorerMainContent } from "./ExplorerMainContent";
import { ExplorerSidebar } from "./ExplorerSidebar";
import { useExplorerWorkflow } from "./hooks/useExplorerWorkflow";
import { ReviewerPreviewOverlay } from "./ReviewerPreviewOverlay";

interface ExplorerProps {
  onBack: () => void;
  sealedDemoRee: Ree;
  PodOrbitControl: React.ComponentType<{
    level: number;
    levelMeta: import("../../types").Level;
    stepStates: Record<string, import("../../types").StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

export function ExplorerView({ onBack, sealedDemoRee, PodOrbitControl }: ExplorerProps) {
  const { state, dispatch } = useAppContext();
  const explorer = explorerSelectors.state(state);
  const {
    ree,
    locked,
    actionStates,
    badges,
    timestamps,
    serviceLogs,
    serviceParams,
    toast,
    page,
    repoMode,
    focusedField,
    navCollapsed,
    virtualFiles,
    immutableSourceSnapshotFiles,
    immutableSourceSnapshotArchiveName,
    showReviewerPreview,
  } = explorer;

  const onPageChange: React.Dispatch<React.SetStateAction<ExplorerPage>> = (page) => {
    dispatch(explorerActions.setPage(page));
  };
  const onNavCollapsedChange: React.Dispatch<React.SetStateAction<boolean>> = (navCollapsed) => {
    dispatch(explorerActions.setNavCollapsed(navCollapsed));
  };
  const onReeChange: React.Dispatch<React.SetStateAction<Ree>> = (ree) => {
    dispatch(explorerActions.setRee(ree));
  };
  const onLockedChange: React.Dispatch<React.SetStateAction<boolean>> = (locked) => {
    dispatch(explorerActions.setLocked(locked));
  };
  const onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">> = (repoMode) => {
    dispatch(explorerActions.setRepoMode(repoMode));
  };
  const onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>> = (
    focusedField,
  ) => {
    dispatch(explorerActions.setFocusedField(focusedField));
  };
  const onVirtualFilesChange: React.Dispatch<React.SetStateAction<FileTreeNode[]>> = (
    virtualFiles,
  ) => {
    dispatch(explorerActions.setVirtualFiles(virtualFiles));
  };
  const onServiceParamsChange: React.Dispatch<React.SetStateAction<ServiceParams>> = (
    serviceParams,
  ) => {
    dispatch(explorerActions.setServiceParams(serviceParams));
  };
  const onShowReviewerPreviewChange: React.Dispatch<React.SetStateAction<boolean>> = (
    showReviewerPreview,
  ) => {
    dispatch(explorerActions.setShowReviewerPreview(showReviewerPreview));
  };

  const currentReeArchiveEntries = useMemo(
    () =>
      buildCurrentReeArchiveEntries(
        ree,
        virtualFiles,
        immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName,
      ),
    [ree, virtualFiles, immutableSourceSnapshotFiles, immutableSourceSnapshotArchiveName],
  );
  const currentReeFiles = useMemo(
    () => reeArchiveEntriesToFiles(currentReeArchiveEntries),
    [currentReeArchiveEntries],
  );

  const level = ree._evalLevel ?? 0;
  const {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    runAction,
  } = useExplorerWorkflow({
    dispatch,
    ree,
    level,
    virtualFiles,
    serviceParams,
    currentReeArchiveEntries,
  });

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
          REE Explorer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        <ExplorerSidebar
          page={page}
          ree={ree}
          navCollapsed={navCollapsed}
          actionStates={actionStates}
          badges={badges}
          timestamps={timestamps}
          setPage={onPageChange}
          setNavCollapsed={onNavCollapsedChange}
          onDownloadRee={handleDownloadRee}
          onPreviewReviewer={() => onShowReviewerPreviewChange(true)}
        />

        <ExplorerMainContent
          page={page}
          ree={ree}
          level={level}
          locked={locked}
          repoMode={repoMode}
          focusedField={focusedField}
          badges={badges}
          timestamps={timestamps}
          serviceLogs={serviceLogs}
          serviceParams={serviceParams}
          actionStates={actionStates}
          virtualFiles={virtualFiles}
          immutableSourceSnapshotFiles={immutableSourceSnapshotFiles}
          currentReeFiles={currentReeFiles}
          onReeChange={onReeChange}
          onLockedChange={onLockedChange}
          onRepoModeChange={onRepoModeChange}
          onPageChange={onPageChange}
          onFocusedFieldChange={onFocusedFieldChange}
          onVirtualFilesChange={onVirtualFilesChange}
          onServiceParamsChange={onServiceParamsChange}
          onSeal={handleSeal}
          onDownloadRee={handleDownloadRee}
          onPreviewReviewer={() => onShowReviewerPreviewChange(true)}
          onDownloadSourceFiles={handleDownloadSourceFiles}
          onWorkspaceUpload={handleWorkspaceUpload}
          onRemoveWorkspaceSource={handleRemoveWorkspaceSource}
          onRunAction={runAction}
        />
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => dispatch(explorerActions.setToast(null))}
        />
      )}

      <ReviewerPreviewOverlay
        open={showReviewerPreview}
        ree={ree}
        onClose={() => onShowReviewerPreviewChange(false)}
        defaultRee={sealedDemoRee}
        PodOrbitControl={PodOrbitControl}
      />
    </div>
  );
}

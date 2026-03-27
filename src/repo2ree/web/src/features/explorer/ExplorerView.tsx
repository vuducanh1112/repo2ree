import type React from "react";
import { useMemo } from "react";
import { Ic } from "../../components/Icon";
import { Toast } from "../../components/Toast";
import { C, F, hoverBg, hoverColor } from "../../constants/theme";
import { useAppContext } from "../../context";
import type { Ree } from "../../types";
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
  const {
    state: { explorer },
    setRee,
    setLocked,
    setRepoMode,
    setActionStates,
    setBadges,
    setTimestamps,
    setServiceLogs,
    setServiceParams,
    setToast,
    setExplorerPage,
    setFocusedField,
    setNavCollapsed,
    setVirtualFiles,
    setImmutableSourceSnapshotFiles,
    setImmutableSourceSnapshotArchiveName,
    setShowReviewerPreview,
  } = useAppContext();
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
  const setPage = setExplorerPage;

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
    ree,
    level,
    virtualFiles,
    serviceParams,
    currentReeArchiveEntries,
    setRee,
    setLocked,
    setActionStates,
    setBadges,
    setTimestamps,
    setServiceLogs,
    setServiceParams,
    setToast,
    setVirtualFiles,
    setImmutableSourceSnapshotFiles,
    setImmutableSourceSnapshotArchiveName,
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
          setPage={setPage}
          setNavCollapsed={setNavCollapsed}
          onDownloadRee={handleDownloadRee}
          onPreviewReviewer={() => setShowReviewerPreview(true)}
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
          setRee={setRee}
          setLocked={setLocked}
          setRepoMode={setRepoMode}
          setPage={setPage}
          setFocusedField={setFocusedField}
          setVirtualFiles={setVirtualFiles}
          setServiceParams={setServiceParams}
          onSeal={handleSeal}
          onDownloadRee={handleDownloadRee}
          onPreviewReviewer={() => setShowReviewerPreview(true)}
          onDownloadSourceFiles={handleDownloadSourceFiles}
          onWorkspaceUpload={handleWorkspaceUpload}
          onRemoveWorkspaceSource={handleRemoveWorkspaceSource}
          onRunAction={runAction}
        />
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <ReviewerPreviewOverlay
        open={showReviewerPreview}
        ree={ree}
        onClose={() => setShowReviewerPreview(false)}
        defaultRee={sealedDemoRee}
        PodOrbitControl={PodOrbitControl}
      />
    </div>
  );
}

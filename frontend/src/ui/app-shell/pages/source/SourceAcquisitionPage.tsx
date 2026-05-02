import type React from "react";
import { useEffect, useState } from "react";
import { PAGE } from "../../../../application/app-shell/AppShellPages";
import { Ic } from "../../../shared/components/Icon";
import { Toggle } from "../../../shared/components/Toggle";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../theme/theme";
import { FieldRow, FieldSection, FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { SourceUploadField, SourceUrlField } from "../../components/sourceRuntime";
import { sourceClearButtonTone, sourceIncludedLabelStyle } from "../../components/statusUiStyles";
import { WorkflowLogSection } from "../../components/workflowRunPanels";
import type { SourceAcquisitionPageProps } from "../sharedWorkflowUi";

const SOURCE_TYPE_OPTIONS = ["git", "hg", "svn", "cvs", "bzr", "tarball", "zip"] as const;
type SourceTypeOption = (typeof SOURCE_TYPE_OPTIONS)[number];

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

export function SourceAcquisitionPage({
  ree,
  workspaceSourceState,
  locked,
  repoMode,
  badges,
  actionStates,
  log,
  running,
  focusedField,
  onReeChange,
  onRepoModeChange,
  onGoWorkflow,
  onFocusedFieldChange,
  onDownloadSource,
  onCancelSource,
  onWorkspaceUpload,
  onRemoveWorkspaceSource,
}: SourceAcquisitionPageProps) {
  const downloadRunning = actionStates.source === "loading";

  const focus = (key: string) => onFocusedFieldChange(key);
  const [originTypeDraft, setOriginTypeDraft] = useState<SourceTypeOption | "">(
    ree.source_type || "",
  );
  const [originUrlDraft, setOriginUrlDraft] = useState(ree.origin_url || "");
  const sourceInWorkspace = !!workspaceSourceState.sourceAvailable;
  const sourceIncluded = sourceInWorkspace && !!workspaceSourceState.sourceIncluded;
  const sourceFromUpload = workspaceSourceState.sourceAcquiredBy === "upload" && sourceInWorkspace;
  const sourceFromDownload =
    workspaceSourceState.sourceAcquiredBy === "download" && sourceInWorkspace;
  const sourceConfigLocked = sourceInWorkspace;
  const downloadDone = sourceFromDownload;
  const sourceInteractionLocked = locked || sourceConfigLocked;

  const toggleSourceIncluded = () => {
    focus("sourceAvailable");
    if (locked || !sourceInWorkspace || workspaceSourceState.sourceAcquiredBy === "upload") return;
    onReeChange({ ...ree, sourceIncluded: !sourceIncluded });
  };

  useEffect(() => {
    if (!sourceInWorkspace && workspaceSourceState.sourceIncluded) {
      onReeChange({ ...ree, sourceIncluded: false });
    }
  }, [sourceInWorkspace, workspaceSourceState.sourceIncluded, ree, onReeChange]);

  useEffect(() => {
    setOriginTypeDraft(ree.source_type || "");
  }, [ree.source_type]);

  useEffect(() => {
    setOriginUrlDraft(ree.origin_url || "");
  }, [ree.origin_url]);

  useFocusScroll(focusedField);

  const originInputLocked = locked || sourceInWorkspace;
  const sourceIncludedLocked = locked || !sourceInWorkspace || sourceFromUpload;
  const sourceIncludedEffective = sourceFromUpload ? true : sourceIncluded;
  const step3Ready = sourceInWorkspace;
  const canDownload =
    !!originUrlDraft && !!originTypeDraft && repoMode === "url" && !sourceInWorkspace;
  const canUpload = repoMode === "upload" && !sourceInWorkspace;
  const downloadLabel = downloadRunning
    ? "Downloading source..."
    : sourceFromDownload
      ? "Source downloaded"
      : sourceFromUpload
        ? "Source currently from upload"
        : "Download source to workspace";

  const acquisitionNarrative = sourceFromUpload
    ? "Source arrived from an uploaded archive."
    : sourceFromDownload
      ? "Source was fetched from origin into this workspace."
      : "No source snapshot yet — choose a method above to continue.";

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <WorkflowPageHeader
        color="#f59e0b"
        icon={Ic.globe(18)}
        title="Source Acquisition"
        subtitle="Tell the source story in three steps: choose, acquire, then confirm snapshot behavior"
        tips={[
          "Pick one acquisition path and complete it end-to-end before moving on.",
          "Once source is present, decide whether that snapshot is included in the final REE archive.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <FieldSection
              title="Step 1: Choose Source Path"
              subtitle={
                sourceConfigLocked ? (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "2px 8px",
                      borderRadius: 999,
                      border: "1px solid #fdba74",
                      background: "#fff7ed",
                      color: "#c2410c",
                      fontSize: 11,
                      fontWeight: 700,
                      lineHeight: 1.2,
                      marginLeft: 4,
                    }}
                  >
                    {Ic.lock(11)} Source configuration is locked. Clear the current workspace source
                    to change it.
                  </span>
                ) : undefined
              }
              filledCount={repoMode ? 1 : 0}
              totalCount={1}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "10px 0" }}>
                <div style={{ display: "flex", gap: 8 }}>
                  {(["url", "upload"] as const).map((m) => {
                    const active = repoMode === m;
                    return (
                      <button
                        type="button"
                        key={m}
                        onClick={() => {
                          focus("sourceAcquiredBy");
                          if (sourceInteractionLocked || m === repoMode) return;
                          onRepoModeChange(m);
                          if (m === "upload") {
                            setOriginTypeDraft("");
                            setOriginUrlDraft("");
                          }
                        }}
                        style={{
                          ...actionBtn({ padding: "8px 10px", fontWeight: active ? 800 : 700 }),
                          flex: 1,
                          cursor: sourceInteractionLocked ? "not-allowed" : "pointer",
                          border: `1.5px solid ${active ? C.accent : C.border}`,
                          background: active ? C.accentBg : C.surface,
                          color: active ? C.accent : C.textMid,
                          opacity: sourceInteractionLocked ? 0.5 : 1,
                        }}
                      >
                        {m === "url" ? "Use origin URL" : "Upload tarball"}
                      </button>
                    );
                  })}
                </div>

                <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                  {repoMode === "url"
                    ? "Point to an origin and fetch files into this workspace."
                    : "Bring a source snapshot directly from a local tarball."}
                </div>
              </div>
            </FieldSection>

            <div style={{ marginTop: 12 }}>
              <FieldSection
                title="Step 2: Acquire Source Snapshot"
                filledCount={sourceInWorkspace ? 1 : 0}
                totalCount={1}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 10,
                    flexWrap: "wrap",
                  }}
                ></div>

                {repoMode === "url" && (
                  <FieldRow
                    fieldKey="origin_url"
                    locked={locked}
                    onFocus={() => focus("origin_url")}
                    active={focusedField === "origin_url"}
                  >
                    <SourceUrlField
                      locked={originInputLocked}
                      committedValue={originUrlDraft}
                      onCommit={(v) => {
                        setOriginUrlDraft(v);
                      }}
                      onFocus={() => focus("origin_url")}
                    />
                    {sourceConfigLocked && (
                      <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                        Origin URL is locked after source is loaded. Clear workspace source to set a
                        different URL.
                      </div>
                    )}
                  </FieldRow>
                )}

                {repoMode === "url" ? (
                  <FieldRow
                    fieldKey="source_type"
                    locked={locked}
                    onFocus={() => focus("source_type")}
                    active={focusedField === "source_type"}
                  >
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <select
                        disabled={locked || sourceConfigLocked}
                        value={originTypeDraft}
                        onChange={(event) => {
                          setOriginTypeDraft(event.target.value as SourceTypeOption | "");
                        }}
                        onFocus={() => focus("source_type")}
                        style={{ ...inp(locked || sourceConfigLocked), flex: 1 }}
                      >
                        <option value="">Select origin type</option>
                        {SOURCE_TYPE_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>

                      <button
                        type="button"
                        disabled={locked || !canDownload || downloadRunning}
                        onClick={() => onDownloadSource(originTypeDraft, originUrlDraft)}
                        style={{
                          ...actionBtn({ fontWeight: 800 }),
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          cursor: locked || !canDownload || downloadRunning ? "default" : "pointer",
                          border: `1.5px solid ${downloadDone ? "#22c55e" : C.accent}`,
                          background: downloadDone ? "#f0fdf4" : C.accentBg,
                          color: downloadDone ? "#15803d" : C.accent,
                          width: "fit-content",
                          opacity: locked || !canDownload ? 0.6 : 1,
                        }}
                      >
                        {downloadRunning ? Ic.loader(13) : Ic.download(13)}
                        {downloadLabel}
                      </button>

                      {downloadRunning && (
                        <button
                          type="button"
                          onClick={onCancelSource}
                          style={{
                            ...actionBtn({ fontWeight: 700, padding: "8px 12px" }),
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            border: "1.5px solid #fecdd3",
                            background: "#fff1f2",
                            color: "#be123c",
                            cursor: "pointer",
                          }}
                        >
                          {Ic.x(12)} Cancel
                        </button>
                      )}
                    </div>
                  </FieldRow>
                ) : (
                  <SourceUploadField
                    locked={locked}
                    disabled={!canUpload}
                    disabledReason={
                      sourceInWorkspace
                        ? "Source is already loaded in workspace. Clear workspace source to switch method."
                        : undefined
                    }
                    committedName={workspaceSourceState.uploadedArchive}
                    onCommit={(payload) => {
                      onWorkspaceUpload(payload);
                    }}
                  />
                )}
              </FieldSection>
            </div>

            <div style={{ marginTop: 12 }}>
              <FieldSection
                title="Step 3: Workspace Actions"
                filledCount={sourceInWorkspace ? 1 : 0}
                totalCount={1}
              >
                {step3Ready ? (
                  <div
                    style={{ display: "flex", flexDirection: "column", gap: 10, padding: "10px 0" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 10,
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                        <span style={sourceIncludedLabelStyle(sourceIncludedEffective)}>
                          Include snapshot in REE
                        </span>
                        <Toggle
                          on={sourceIncludedEffective}
                          disabled={sourceIncludedLocked}
                          color="#f59e0b"
                          onChange={toggleSourceIncluded}
                          title={
                            sourceFromUpload
                              ? "Uploads are always included in final REE to preserve source."
                              : !sourceInWorkspace
                                ? "Load source into workspace first"
                                : sourceIncludedEffective
                                  ? "Source will be included in final REE"
                                  : "Source will be excluded from final REE"
                          }
                          width={36}
                          height={18}
                          knobSize={14}
                        />
                        {sourceFromUpload && (
                          <span style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                            Uploaded source is always included so the archive remains reproducible.
                          </span>
                        )}
                      </div>
                    </div>

                    <div style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans }}>
                      {acquisitionNarrative}
                    </div>

                    <div
                      style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          focus("sourceAvailable");
                          onGoWorkflow(PAGE.FILES);
                        }}
                        style={{
                          ...actionBtn({
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            cursor: "pointer",
                          }),
                          border: `1.5px solid ${C.border}`,
                          background: C.surface,
                          color: C.textMid,
                        }}
                        title="Browse files"
                      >
                        {Ic.files(12)} Browse workspace files
                      </button>

                      {workspaceSourceState.sourceAvailable && (
                        <button
                          type="button"
                          disabled={locked}
                          onClick={() => {
                            focus("sourceAvailable");
                            onRemoveWorkspaceSource();
                          }}
                          style={{
                            ...actionBtn({
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 7,
                              padding: "8px 12px",
                              fontWeight: 800,
                            }),
                            ...sourceClearButtonTone(locked),
                          }}
                        >
                          {Ic.x(12)} Clear workspace source
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "10px 0",
                      fontSize: 12,
                      color: C.textMuted,
                      fontFamily: F.sans,
                    }}
                  >
                    Complete Step 2 to unlock this step.
                  </div>
                )}
              </FieldSection>
            </div>

            <div style={{ marginTop: 12 }}>
              <WorkflowLogSection log={log} running={running} title="Source acquisition logs" />
            </div>

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey={PAGE.SOURCE} badges={badges} onGo={onGoWorkflow} />
            </div>
          </div>
        </div>

        {focusedField && (
          <FieldTipsSidebar
            tipFields={["origin_url", "source_type", "sourceAcquiredBy", "sourceAvailable"]}
            focusedField={focusedField}
            onClear={() => onFocusedFieldChange(null)}
          />
        )}
      </div>
    </div>
  );
}

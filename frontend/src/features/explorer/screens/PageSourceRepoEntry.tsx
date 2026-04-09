import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../../../components/Icon";
import { Toggle } from "../../../components/Toggle";
import { PAGE } from "../../../constants/pages";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../constants/theme";
import { useFocusScroll } from "../../../hooks/useFocusScroll";
import { LogPanel } from "../components/inputs/logPanel";
import { SourceUploadField, SourceUrlField } from "../components/inputs/sourceRuntime";
import { FieldRow, FieldTipsSidebar } from "../components/workflow/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../components/workflow/pageChrome";
import type { PageSourceRepoEntryProps } from "./sharedWorkflowUi";

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

const chapterCard = (active: boolean): React.CSSProperties => ({
  border: `1.5px solid ${active ? C.accentBorder : C.border}`,
  background: active ? C.accentBg : C.surface,
  borderRadius: 12,
  padding: 14,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  boxShadow: active ? "0 8px 20px rgba(37,99,235,0.07)" : "0 4px 12px rgba(15,23,42,0.04)",
  transition: "border-color 0.2s, background 0.2s, box-shadow 0.2s",
});

const statusChip = (active: boolean, tone: "neutral" | "good" | "warn"): React.CSSProperties => {
  const toneColor =
    tone === "good"
      ? { border: "#bbf7d0", bg: "#f0fdf4", text: "#166534" }
      : tone === "warn"
        ? { border: "#fde68a", bg: "#fffbeb", text: "#92400e" }
        : { border: C.border, bg: C.surfaceAlt, text: C.textMid };
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    border: `1px solid ${active ? toneColor.border : C.border}`,
    background: active ? toneColor.bg : C.surface,
    color: active ? toneColor.text : C.textMuted,
    borderRadius: 999,
    padding: "5px 10px",
    fontSize: 12,
    fontWeight: 700,
    fontFamily: F.sans,
  };
};

export function PageSourceRepoEntry({
  ree,
  locked,
  repoMode,
  badges,
  actionStates,
  log,
  running,
  focusedField,
  onReeChange,
  onRepoModeChange,
  onGoService,
  onFocusedFieldChange,
  onDownloadSource,
  onCancelSource,
  onWorkspaceUpload,
  onRemoveWorkspaceSource,
}: PageSourceRepoEntryProps) {
  const onChange = onReeChange;
  const downloadRunning = actionStates.source === "loading";
  const downloadDone = !!ree._sourceAvailable;

  const focus = (key: string) => onFocusedFieldChange(key);
  const [originTypeDraft, setOriginTypeDraft] = useState<
    "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball" | ""
  >(ree.source_type || "");
  const [originUrlDraft, setOriginUrlDraft] = useState(ree.origin_url || "");
  const sourceInWorkspace = !!ree._sourceAvailable;
  const sourceIncluded = sourceInWorkspace && !!ree._sourceIncluded;
  const toggleSourceIncluded = () => {
    focus("_sourceAvailable");
    if (locked || !sourceInWorkspace || ree._sourceAcquiredBy === "upload") return;
    onChange({ ...ree, _sourceIncluded: !sourceIncluded });
  };

  useEffect(() => {
    if (!sourceInWorkspace && ree._sourceIncluded) {
      onChange({ ...ree, _sourceIncluded: false });
    }
  }, [sourceInWorkspace, ree, onChange]);

  useEffect(() => {
    setOriginTypeDraft(ree.source_type || "");
  }, [ree.source_type]);

  useEffect(() => {
    setOriginUrlDraft(ree.origin_url || "");
  }, [ree.origin_url]);

  useFocusScroll(focusedField);

  const sourceFromUpload = ree._sourceAcquiredBy === "upload" && !!ree._sourceAvailable;
  const sourceFromDownload = ree._sourceAcquiredBy === "download" && !!ree._sourceAvailable;
  const sourceConfigLocked = sourceInWorkspace;
  const originInputLocked = locked || sourceInWorkspace;
  const sourceIncludedLocked = locked || !sourceInWorkspace || sourceFromUpload;
  const sourceIncludedEffective = sourceFromUpload ? true : sourceIncluded;
  const workspaceLoadProgress = sourceInWorkspace ? 1 : 0;
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
        title="Source Repo"
        subtitle="Tell the source story in three steps: choose, acquire, then confirm snapshot behavior"
        tips={[
          "Pick one acquisition path and complete it end-to-end before moving on.",
          "Once source is present, decide whether that snapshot is included in the final REE archive.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 10,
                padding: "0 2px",
              }}
            >
              <div style={{ fontFamily: F.sans, fontSize: 13, color: C.textMid, fontWeight: 700 }}>
                Workspace Source Progress
              </div>
              <div style={{ fontFamily: F.mono, fontSize: 12, color: C.textMuted }}>
                {workspaceLoadProgress}/1 loaded
              </div>
            </div>

            <div
              style={chapterCard(
                focusedField === "origin_url" || focusedField === "_sourceAcquiredBy",
              )}
            >
              <div
                style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
              >
                <div style={{ fontFamily: F.sans, fontWeight: 800, color: C.text }}>
                  1. Choose source path
                </div>
                <span style={{ ...statusChip(true, "neutral") }}>
                  {repoMode === "url" ? Ic.globe(12) : Ic.upload(12)}{" "}
                  {repoMode === "url" ? "Origin URL" : "Upload archive"}
                </span>
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                {(["url", "upload"] as const).map((m) => {
                  const active = repoMode === m;
                  return (
                    <button
                      type="button"
                      key={m}
                      onClick={() => {
                        focus("_sourceAcquiredBy");
                        if (locked || sourceConfigLocked || m === repoMode) return;
                        onRepoModeChange(m);
                        if (m === "upload") {
                          setOriginTypeDraft("");
                          setOriginUrlDraft("");
                        }
                      }}
                      style={{
                        ...actionBtn({ padding: "8px 10px", fontWeight: active ? 800 : 700 }),
                        flex: 1,
                        cursor: locked || sourceConfigLocked ? "not-allowed" : "pointer",
                        border: `1.5px solid ${active ? C.accent : C.border}`,
                        background: active ? C.accentBg : C.surface,
                        color: active ? C.accent : C.textMid,
                        opacity: locked || sourceConfigLocked ? 0.5 : 1,
                      }}
                    >
                      {m === "url" ? "Use origin URL" : "Upload tarball"}
                    </button>
                  );
                })}
              </div>

              {sourceConfigLocked && (
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 7,
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1.5px solid #fde68a",
                    background: "#fffbeb",
                    color: "#92400e",
                    fontSize: 12,
                    fontFamily: F.sans,
                    fontWeight: 700,
                  }}
                >
                  {Ic.lock(12)} Source configuration is locked until workspace source is cleared.
                </div>
              )}

              <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                {repoMode === "url"
                  ? "Point to an origin and fetch files into this workspace."
                  : "Bring a source snapshot directly from a local tarball."}
              </div>
            </div>

            <div
              style={{
                ...chapterCard(focusedField === "source_type" || focusedField === "origin_url"),
                marginTop: 12,
              }}
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
                <div style={{ fontFamily: F.sans, fontWeight: 800, color: C.text }}>
                  2. Acquire source snapshot
                </div>
              </div>

              {sourceFromUpload && (
                <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                  Uploaded source is always included so the archive remains reproducible.
                </div>
              )}
              <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                {sourceIncludedEffective
                  ? "Including source in the REE keeps reproduction independent of future origin availability."
                  : "If source is excluded from the REE, reproduction may depend on origin availability later."}
              </div>

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
                  required
                  locked={locked}
                  onFocus={() => focus("source_type")}
                  active={focusedField === "source_type"}
                >
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <select
                      disabled={locked || sourceConfigLocked}
                      value={originTypeDraft}
                      onChange={(event) => {
                        setOriginTypeDraft(
                          event.target.value as
                            | "git"
                            | "hg"
                            | "svn"
                            | "cvs"
                            | "bzr"
                            | "tarball"
                            | "",
                        );
                      }}
                      onFocus={() => focus("source_type")}
                      style={{ ...inp(locked || sourceConfigLocked), flex: 1 }}
                    >
                      <option value="">Select origin type</option>
                      <option value="git">git</option>
                      <option value="hg">hg</option>
                      <option value="svn">svn</option>
                      <option value="cvs">cvs</option>
                      <option value="bzr">bzr</option>
                      <option value="tarball">tarball</option>
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
                  committedName={ree._uploadedArchive}
                  onCommit={(payload) => {
                    onWorkspaceUpload(payload);
                  }}
                />
              )}
            </div>

            <div style={{ ...chapterCard(focusedField === "_sourceAvailable"), marginTop: 12 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ fontFamily: F.sans, fontWeight: 800, color: C.text }}>
                  3. Workspace actions
                </div>
                <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: sourceIncludedEffective ? "#b45309" : C.textMid,
                      fontFamily: F.sans,
                    }}
                  >
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
                </div>
              </div>

              <div style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans }}>
                {acquisitionNarrative}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => {
                    focus("_sourceAvailable");
                    onGoService(PAGE.FILES);
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

                {ree._sourceAvailable && (
                  <button
                    type="button"
                    disabled={locked}
                    onClick={() => {
                      focus("_sourceAvailable");
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
                      border: "1.5px solid #fca5a5",
                      background: "#fee2e2",
                      color: "#991b1b",
                      cursor: locked ? "not-allowed" : "pointer",
                      opacity: locked ? 0.6 : 1,
                    }}
                  >
                    {Ic.x(12)} Clear workspace source
                  </button>
                )}
              </div>

              <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                {sourceIncludedEffective
                  ? "The original source snapshot will be packaged into the final REE archive (workspace edits are excluded)."
                  : "Source files remain available for local work but are excluded from the final REE archive."}
              </div>
            </div>

            <div style={{ ...chapterCard(false), marginTop: 12 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ fontFamily: F.sans, fontWeight: 800, color: C.text }}>
                  Source acquisition logs
                </div>
                <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                  {running ? "Streaming" : "Latest run"}
                </div>
              </div>
              <LogPanel log={log} running={running} />
            </div>

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey={PAGE.SOURCE} badges={badges} onGo={onGoService} />
            </div>
          </div>
        </div>

        {focusedField && (
          <FieldTipsSidebar
            tipFields={["origin_url", "source_type", "_sourceAcquiredBy", "_sourceAvailable"]}
            focusedField={focusedField}
            onClear={() => onFocusedFieldChange(null)}
          />
        )}
      </div>
    </div>
  );
}

import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../../../components/Icon";
import { Toggle } from "../../../components/Toggle";
import { PAGE } from "../../../constants/pages";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  S_ACTION_BUTTON_BASE,
  S_SECTION_LABEL_SMALL,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../constants/theme";
import { useFocusScroll } from "../../../hooks/useFocusScroll";
import { SourceUploadField, SourceUrlField } from "../components/inputs/sourceRuntime";
import { FieldRow, FieldSection, FieldTipsSidebar } from "../components/workflow/fieldTips";
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

export function PageSourceRepoEntry({
  ree,
  locked,
  repoMode,
  badges,
  actionStates,
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

  const set = <K extends keyof typeof ree>(k: K, v: (typeof ree)[K]) =>
    onChange({ ...ree, [k]: v } as typeof ree);
  const focus = (key: string) => onFocusedFieldChange(key);
  const [originTypeDraft, setOriginTypeDraft] = useState<
    "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball" | ""
  >(ree.source_type || "");
  const sourceInWorkspace = !!ree._sourceAvailable;
  const sourceIncluded = sourceInWorkspace && !!ree._sourceIncluded;
  const toggleSourceIncluded = () => {
    if (locked || !sourceInWorkspace) return;
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

  useFocusScroll(focusedField);

  const sourceFromUpload = ree._sourceAcquiredBy === "upload" && !!ree._sourceAvailable;
  const sourceFromDownload = ree._sourceAcquiredBy === "download" && !!ree._sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";
  const sourceFilled = [
    ree.origin_url,
    ree._sourceAcquiredBy,
    ree._sourceAvailable ? "yes" : "",
  ].filter(Boolean).length;
  const canDownload =
    !!ree.origin_url && !!originTypeDraft && repoMode === "url" && !sourceFromUpload;
  const canUpload = repoMode === "upload" && !sourceFromDownload;
  const downloadLabel = downloadRunning
    ? "Downloading source..."
    : sourceFromUpload
      ? "Source uploaded"
      : sourceFromDownload
        ? "Source downloaded"
        : "Download source files locally";

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <WorkflowPageHeader
        color="#f59e0b"
        icon={Ic.globe(18)}
        title="Source Repo"
        subtitle="Set origin, source type, and populate source files into the workspace"
        tips={[
          "Bring source code into the local workspace before any downstream step.",
          "Choose one acquisition path (download from origin or upload archive) and keep it consistent.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <FieldSection
              title="Source Repository"
              icon={Ic.globe()}
              filledCount={sourceFilled}
              totalCount={3}
            >
              <FieldRow
                fieldKey="origin_url"
                locked={locked}
                onFocus={() => focus("origin_url")}
                active={focusedField === "origin_url"}
              >
                <SourceUrlField
                  locked={locked}
                  committedValue={ree.origin_url}
                  onCommit={(v) => {
                    set("origin_url", v);
                  }}
                  onFocus={() => focus("origin_url")}
                />
              </FieldRow>

              <div style={{ padding: "12px 0 0" }}>
                <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                  {(["url", "upload"] as const).map((m) => (
                    <button
                      type="button"
                      key={m}
                      onClick={() => {
                        if (locked || m === repoMode) return;
                        onRepoModeChange(m);
                        if (m === "upload") setOriginTypeDraft("");
                      }}
                      style={{
                        ...actionBtn({
                          padding: "7px",
                        }),
                        flex: 1,
                        cursor: locked ? "default" : "pointer",
                        border: `1.5px solid ${repoMode === m ? C.accent : C.border}`,
                        background: repoMode === m ? C.accentBg : C.surface,
                        color: repoMode === m ? C.accent : C.textMid,
                      }}
                    >
                      {m === "url" ? "⇢ Origin URL" : "⤒ Upload tarball"}
                    </button>
                  ))}
                </div>
                {downloadRunning && (
                  <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      onClick={onCancelSource}
                      style={{
                        ...actionBtn({
                          fontWeight: 700,
                          padding: "7px 12px",
                        }),
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        border: "1.5px solid #fecdd3",
                        background: "#fff1f2",
                        color: "#be123c",
                        cursor: "pointer",
                      }}
                    >
                      {Ic.x(12)} Cancel current source operation
                    </button>
                  </div>
                )}
              </div>
              {repoMode === "upload" && (
                <SourceUploadField
                  locked={locked}
                  disabled={!canUpload}
                  disabledReason={
                    sourceFromDownload
                      ? "Source is already populated via origin download. Change source to switch method."
                      : undefined
                  }
                  committedName={ree._uploadedArchive}
                  onCommit={(payload) => {
                    onWorkspaceUpload(payload);
                  }}
                />
              )}

              {repoMode === "url" && (
                <FieldRow
                  fieldKey="source_type"
                  required
                  locked={locked}
                  onFocus={() => focus("source_type")}
                  active={focusedField === "source_type"}
                >
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <select
                      disabled={locked}
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
                      style={{ ...inp(locked), flex: 1 }}
                    >
                      <option value="">Select origin type</option>
                      <option value="git">git</option>
                      <option value="hg">hg</option>
                      <option value="svn">svn</option>
                      <option value="cvs">cvs</option>
                      <option value="bzr">bzr</option>
                      <option value="tarball">tarball</option>
                    </select>

                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button
                          type="button"
                          disabled={locked || !canDownload || downloadRunning}
                          onClick={() => onDownloadSource(originTypeDraft)}
                          style={{
                            ...actionBtn({
                              fontWeight: 700,
                            }),
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
                              ...actionBtn({
                                fontWeight: 700,
                                padding: "8px 12px",
                              }),
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
                    </div>
                  </div>
                </FieldRow>
              )}

              <FieldRow fieldKey="_sourceAcquiredBy" required={false} locked={true}>
                <input
                  disabled
                  value={sourceProvisionStatus}
                  style={{
                    ...inp(true, {
                      cursor: "not-allowed",
                      color: sourceInWorkspace ? C.text : C.textMuted,
                      fontWeight: 600,
                    }),
                  }}
                />
              </FieldRow>

              <FieldRow
                fieldKey="_sourceAvailable"
                required={false}
                locked={true}
                onFocus={() => focus("_sourceAvailable")}
                active={focusedField === "_sourceAvailable"}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <button
                      type="button"
                      onClick={() => onGoService(PAGE.FILES)}
                      style={{
                        ...inp(false, {
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 8,
                          cursor: "pointer",
                        }),
                        background: C.surface,
                        borderColor: C.border,
                        flex: 1,
                      }}
                      title="Browse files"
                      {...hoverBg(C.accentBg, C.surface)}
                      {...hoverBorderColor(C.accentBorder, C.border)}
                    >
                      <span
                        style={{
                          color: sourceInWorkspace ? "#15803d" : C.textMuted,
                          fontWeight: 600,
                          fontFamily: F.sans,
                        }}
                      >
                        {sourceInWorkspace
                          ? "Yes — repository is available in workspace"
                          : "No — source not in workspace yet"}
                      </span>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          color: C.accent,
                          fontSize: 12,
                          fontWeight: 700,
                          fontFamily: F.sans,
                          flexShrink: 0,
                        }}
                      >
                        {Ic.files(12)} Browse files
                      </span>
                    </button>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginLeft: 2,
                        flexShrink: 0,
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        <div
                          style={{
                            ...S_SECTION_LABEL_SMALL,
                            letterSpacing: 0.7,
                            color: sourceIncluded ? C.textMid : C.textMuted,
                          }}
                        >
                          Included
                        </div>
                        <div
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: sourceIncluded ? "#b45309" : C.textMuted,
                            fontFamily: F.sans,
                          }}
                        >
                          {sourceIncluded ? "Yes" : "No"}
                        </div>
                      </div>
                      <Toggle
                        on={sourceIncluded}
                        disabled={locked || !sourceInWorkspace}
                        color="#f59e0b"
                        onChange={toggleSourceIncluded}
                        title={
                          !sourceInWorkspace
                            ? "Source must be in workspace before it can be included"
                            : sourceIncluded
                              ? "Source will be included in final REE"
                              : "Source will be excluded from final REE"
                        }
                        width={36}
                        height={18}
                        knobSize={14}
                      />
                      {ree._sourceAvailable && (
                        <button
                          type="button"
                          disabled={locked}
                          onClick={onRemoveWorkspaceSource}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            width: "fit-content",
                            padding: "6px 10px",
                            borderRadius: 6,
                            border: "1px solid #fecaca",
                            background: "#fef2f2",
                            color: "#b91c1c",
                            fontSize: 12,
                            fontFamily: F.sans,
                            fontWeight: 600,
                            cursor: locked ? "not-allowed" : "pointer",
                            opacity: locked ? 0.6 : 1,
                          }}
                        >
                          {Ic.x(12)} Remove source from workspace
                        </button>
                      )}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                    {sourceIncluded
                      ? "Original source snapshot will be packaged into the final REE archive (workspace edits are excluded)."
                      : "Source files stay in workspace only and are excluded from the final REE archive."}
                  </div>
                </div>
              </FieldRow>
            </FieldSection>

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey={PAGE.SOURCE} badges={badges} onGo={onGoService} />
            </div>
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["origin_url", "source_type", "_sourceAcquiredBy", "_sourceAvailable"]}
          focusedField={focusedField}
          onClear={() => onFocusedFieldChange(null)}
        />
      </div>
    </div>
  );
}

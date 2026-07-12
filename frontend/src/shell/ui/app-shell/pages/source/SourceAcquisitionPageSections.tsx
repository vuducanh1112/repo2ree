import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgInput, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import type React from "react";
import { SourceUploadField } from "../../components/sourceRuntime/SourceUploadField";
import { SourceUrlField } from "../../components/sourceRuntime/SourceUrlField";
import type { SourceAcquisitionPageProps } from "../sharedStepUi";
import { SOURCE_TYPE_OPTIONS, type SourceTypeOption } from "./SourceAcquisitionPageHelpers";

interface SourceAcquisitionCardProps {
  repoMode: "url" | "upload";
  sourceConfigLocked: boolean;
  sourceInteractionLocked: boolean;
  sourceInWorkspace: boolean;
  locked: boolean;
  focusedField: string | null;
  originUrlDraft: string;
  originTypeDraft: SourceTypeOption | "";
  revisionDraft: string;
  resolvedRevision: string;
  originInputLocked: boolean;
  priorOriginUrl: string;
  canDownload: boolean;
  canUpload: boolean;
  downloadRunning: boolean;
  downloadDone: boolean;
  downloadLabel: string;
  workspaceSourceState: SourceAcquisitionPageProps["workspaceSourceState"];
  focus: (key: string) => void;
  onRepoModeChange: (mode: "url" | "upload") => void;
  setOriginUrlDraft: (value: string) => void;
  setOriginTypeDraft: (value: SourceTypeOption | "") => void;
  setRevisionDraft: (value: string) => void;
  onDownloadSource: (
    originType: SourceTypeOption | "",
    originUrl: string,
    revision: string,
  ) => void;
  onCancelSource: () => void;
  onWorkspaceUpload: SourceAcquisitionPageProps["onWorkspaceUpload"];
}

function modeButton(active: boolean, locked: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: "9px 14px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: active ? 800 : 600,
    fontFamily: F.sans,
    cursor: locked ? "not-allowed" : "pointer",
    border: active ? "1px solid rgba(14, 165, 233, 0.45)" : "1px solid rgba(148, 163, 184, 0.34)",
    background: active ? "rgba(239, 246, 255, 0.88)" : "rgba(255, 255, 255, 0.54)",
    color: active ? lgColors.primaryDeep : lgColors.textMid,
    opacity: locked ? 0.5 : 1,
    transition: "all 0.15s",
  };
}

function downloadButtonStyle(downloadDone: boolean, disabled: boolean): React.CSSProperties {
  return {
    padding: "9px 14px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 800,
    fontFamily: F.sans,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    cursor: disabled ? "not-allowed" : "pointer",
    border: downloadDone
      ? "1px solid rgba(34, 197, 94, 0.42)"
      : "1px solid rgba(14, 165, 233, 0.42)",
    background: downloadDone ? "rgba(240, 253, 244, 0.78)" : "rgba(239, 246, 255, 0.88)",
    color: downloadDone ? lgColors.success : lgColors.primaryDeep,
    opacity: disabled ? 0.6 : 1,
    flexShrink: 0,
  };
}

export function SourceAcquisitionCard(props: SourceAcquisitionCardProps) {
  return (
    <div>
      <div style={{ ...lgStyles.label, marginBottom: 8 }}>Acquisition Method</div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {(["url", "upload"] as const).map((m) => {
          const active = props.repoMode === m;
          return (
            <button
              type="button"
              key={m}
              onClick={() => {
                props.focus("sourceAcquiredBy");
                if (props.sourceInteractionLocked || m === props.repoMode) return;
                props.onRepoModeChange(m);
                if (m === "upload") {
                  props.setOriginTypeDraft("");
                  props.setOriginUrlDraft("");
                }
              }}
              style={modeButton(active, props.sourceInteractionLocked)}
            >
              {m === "url" ? "Use origin URL" : "Upload tarball"}
            </button>
          );
        })}
      </div>

      {props.sourceConfigLocked && (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 10px",
            borderRadius: 999,
            border: "1px solid rgba(245, 158, 11, 0.45)",
            background: "rgba(254, 249, 195, 0.82)",
            color: lgColors.warning,
            fontSize: 11,
            fontWeight: 700,
            marginBottom: 10,
          }}
        >
          {Ic.lock(11)} Configuration locked — clear workspace source to change method
        </div>
      )}

      <div
        style={{
          fontSize: 12,
          color: lgColors.textMuted,
          fontFamily: F.sans,
          marginBottom: 14,
        }}
      >
        {props.repoMode === "url"
          ? "Point to an origin and fetch files into this workspace."
          : "Bring a source snapshot directly from a local tarball."}
      </div>

      <div
        style={{
          borderTop: "1px solid rgba(125, 211, 252, 0.28)",
          paddingTop: 12,
        }}
      >
        <div style={{ ...lgStyles.label, marginBottom: 8 }}>Source Snapshot</div>

        {props.repoMode === "url" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SourceUrlField
              locked={props.originInputLocked}
              value={props.originUrlDraft}
              priorValue={props.priorOriginUrl}
              onChange={(v) => props.setOriginUrlDraft(v)}
              onFocus={() => props.focus("origin_url")}
            />
            {props.sourceConfigLocked && (
              <div style={lgStyles.helper}>
                Origin URL is locked after source is loaded. Clear workspace source to change.
              </div>
            )}
            {props.originTypeDraft === "git" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <input
                  type="text"
                  disabled={props.originInputLocked}
                  value={props.revisionDraft}
                  placeholder="Revision (commit, branch, or tag) — defaults to HEAD"
                  onChange={(e) => props.setRevisionDraft(e.target.value)}
                  onFocus={() => props.focus("revision")}
                  style={lgInput(props.originInputLocked)}
                />
                {!props.sourceConfigLocked && (
                  <div style={lgStyles.helper}>
                    Leave blank to fetch the default branch's latest commit (HEAD).
                  </div>
                )}
                {props.sourceConfigLocked && props.resolvedRevision && (
                  <div style={lgStyles.helper}>
                    Resolved to commit <code>{props.resolvedRevision}</code> — the exact commit a
                    sealed bundle re-fetches.
                  </div>
                )}
              </div>
            )}
            <div
              style={{
                display: "flex",
                gap: 8,
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <select
                disabled={props.locked || props.sourceConfigLocked}
                value={props.originTypeDraft}
                onChange={(e) => props.setOriginTypeDraft(e.target.value as SourceTypeOption | "")}
                onFocus={() => props.focus("source_type")}
                style={{
                  ...lgInput(props.locked || props.sourceConfigLocked),
                  flex: "1 1 140px",
                }}
              >
                <option value="">Select origin type</option>
                {SOURCE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={props.locked || !props.canDownload || props.downloadRunning}
                onClick={() =>
                  props.onDownloadSource(
                    props.originTypeDraft,
                    props.originUrlDraft,
                    props.revisionDraft,
                  )
                }
                style={downloadButtonStyle(props.downloadDone, props.locked || !props.canDownload)}
              >
                {props.downloadRunning ? Ic.loader(13) : Ic.download(13)}
                {props.downloadLabel}
              </button>
              {props.downloadRunning && (
                <button
                  type="button"
                  onClick={props.onCancelSource}
                  style={{
                    padding: "9px 12px",
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 700,
                    fontFamily: F.sans,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    border: "1px solid rgba(251, 113, 133, 0.4)",
                    background: "rgba(255, 241, 242, 0.82)",
                    color: lgColors.danger,
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  {Ic.x(12)} Cancel
                </button>
              )}
            </div>
          </div>
        ) : (
          <SourceUploadField
            locked={props.locked}
            disabled={!props.canUpload}
            disabledReason={
              props.sourceInWorkspace
                ? "Source is already loaded. Clear workspace source to switch method."
                : undefined
            }
            committedName={props.workspaceSourceState.uploadedArchive}
            onCommit={(payload) => props.onWorkspaceUpload(payload)}
          />
        )}
      </div>
    </div>
  );
}

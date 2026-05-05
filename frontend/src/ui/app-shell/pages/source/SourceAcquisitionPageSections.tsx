import { Ic } from "../../../shared/components/Icon";
import { C, F } from "../../../theme/theme";
import { FieldRow, FieldSection } from "../../components/fieldTips";
import { SourceUploadField, SourceUrlField } from "../../components/sourceRuntime";
import type { SourceAcquisitionPageProps } from "../sharedWorkflowUi";
import { SOURCE_TYPE_OPTIONS, type SourceTypeOption } from "./SourceAcquisitionPageHelpers";
import { actionBtn, inputStyle } from "./SourceAcquisitionPageStyles";

interface Step1Props {
  sourceConfigLocked: boolean;
  repoMode: "url" | "upload";
  sourceInteractionLocked: boolean;
  focus: (key: string) => void;
  onRepoModeChange: (mode: "url" | "upload") => void;
  setOriginTypeDraft: (value: SourceTypeOption | "") => void;
  setOriginUrlDraft: (value: string) => void;
}

export function SourceStep1Section(props: Step1Props) {
  const { sourceConfigLocked, repoMode, sourceInteractionLocked, focus } = props;
  return (
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
            {Ic.lock(11)} Source configuration is locked. Clear the current workspace source to
            change it.
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
                  props.onRepoModeChange(m);
                  if (m === "upload") {
                    props.setOriginTypeDraft("");
                    props.setOriginUrlDraft("");
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
  );
}

interface Step2Props {
  repoMode: "url" | "upload";
  sourceInWorkspace: boolean;
  locked: boolean;
  sourceConfigLocked: boolean;
  focusedField: string | null;
  originUrlDraft: string;
  originTypeDraft: SourceTypeOption | "";
  originInputLocked: boolean;
  canDownload: boolean;
  canUpload: boolean;
  downloadRunning: boolean;
  downloadDone: boolean;
  downloadLabel: string;
  workspaceSourceState: SourceAcquisitionPageProps["workspaceSourceState"];
  focus: (key: string) => void;
  setOriginUrlDraft: (value: string) => void;
  setOriginTypeDraft: (value: SourceTypeOption | "") => void;
  onDownloadSource: (originType: SourceTypeOption | "", originUrl: string) => void;
  onCancelSource: () => void;
  onWorkspaceUpload: SourceAcquisitionPageProps["onWorkspaceUpload"];
}

export function SourceStep2Section(props: Step2Props) {
  return (
    <FieldSection
      title="Step 2: Acquire Source Snapshot"
      filledCount={props.sourceInWorkspace ? 1 : 0}
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
      />
      {props.repoMode === "url" && (
        <FieldRow
          fieldKey="origin_url"
          locked={props.locked}
          onFocus={() => props.focus("origin_url")}
          active={props.focusedField === "origin_url"}
        >
          <SourceUrlField
            locked={props.originInputLocked}
            committedValue={props.originUrlDraft}
            onCommit={(v) => props.setOriginUrlDraft(v)}
            onFocus={() => props.focus("origin_url")}
          />
          {props.sourceConfigLocked && (
            <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
              Origin URL is locked after source is loaded. Clear workspace source to set a different
              URL.
            </div>
          )}
        </FieldRow>
      )}

      {props.repoMode === "url" ? (
        <FieldRow
          fieldKey="source_type"
          locked={props.locked}
          onFocus={() => props.focus("source_type")}
          active={props.focusedField === "source_type"}
        >
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <select
              disabled={props.locked || props.sourceConfigLocked}
              value={props.originTypeDraft}
              onChange={(event) =>
                props.setOriginTypeDraft(event.target.value as SourceTypeOption | "")
              }
              onFocus={() => props.focus("source_type")}
              style={{ ...inputStyle(props.locked || props.sourceConfigLocked), flex: 1 }}
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
              disabled={props.locked || !props.canDownload || props.downloadRunning}
              onClick={() => props.onDownloadSource(props.originTypeDraft, props.originUrlDraft)}
              style={{
                ...actionBtn({ fontWeight: 800 }),
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                cursor:
                  props.locked || !props.canDownload || props.downloadRunning
                    ? "default"
                    : "pointer",
                border: `1.5px solid ${props.downloadDone ? "#22c55e" : C.accent}`,
                background: props.downloadDone ? "#f0fdf4" : C.accentBg,
                color: props.downloadDone ? "#15803d" : C.accent,
                width: "fit-content",
                opacity: props.locked || !props.canDownload ? 0.6 : 1,
              }}
            >
              {props.downloadRunning ? Ic.loader(13) : Ic.download(13)}
              {props.downloadLabel}
            </button>
            {props.downloadRunning && (
              <button
                type="button"
                onClick={props.onCancelSource}
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
          locked={props.locked}
          disabled={!props.canUpload}
          disabledReason={
            props.sourceInWorkspace
              ? "Source is already loaded in workspace. Clear workspace source to switch method."
              : undefined
          }
          committedName={props.workspaceSourceState.uploadedArchive}
          onCommit={(payload) => props.onWorkspaceUpload(payload)}
        />
      )}
    </FieldSection>
  );
}

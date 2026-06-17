import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../../../shared/components/Icon";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import { lgColors, lgStatusBadge } from "../../../theme/lightGlassTheme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import type { SourceAcquisitionPageProps } from "../sharedAssemblyUi";
import type { SourceTypeOption } from "./SourceAcquisitionPageHelpers";
import { SourceAcquisitionCard } from "./SourceAcquisitionPageSections";
import { SourceStep3Section } from "./SourceAcquisitionPageStep3Section";

function sourceBadge(sourceInWorkspace: boolean, running: boolean): React.CSSProperties {
  if (running) {
    return {
      border: "1px solid rgba(245, 158, 11, 0.45)",
      borderRadius: 99,
      padding: "3px 8px",
      color: lgColors.warning,
      background: "rgba(254, 249, 195, 0.82)",
      fontSize: 11,
      fontWeight: 700,
    };
  }
  return lgStatusBadge(sourceInWorkspace);
}

function clearSourceButton(locked: boolean): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 13px",
    borderRadius: 8,
    fontSize: 12.5,
    fontWeight: 700,
    border: "1px solid rgba(251, 113, 133, 0.4)",
    background: locked ? "rgba(241, 245, 249, 0.72)" : "rgba(255, 241, 242, 0.82)",
    color: locked ? lgColors.textMuted : lgColors.danger,
    cursor: locked ? "not-allowed" : "pointer",
    flexShrink: 0,
  };
}

export function SourceAcquisitionPage({
  ree,
  workspaceSourceState,
  sourceRepo,
  locked,
  repoMode,
  actionStates,
  log,
  running,
  focusedField,
  onRepoModeChange,
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
  const sourceFromUpload = workspaceSourceState.sourceAcquiredBy === "upload" && sourceInWorkspace;
  const sourceFromDownload =
    workspaceSourceState.sourceAcquiredBy === "download" && sourceInWorkspace;
  const sourceConfigLocked = sourceInWorkspace;
  const downloadDone = sourceFromDownload;
  const sourceInteractionLocked = locked || sourceConfigLocked;

  useEffect(() => {
    setOriginTypeDraft(ree.source_type || "");
  }, [ree.source_type]);

  useEffect(() => {
    setOriginUrlDraft(ree.origin_url || "");
  }, [ree.origin_url]);

  useFocusScroll(focusedField);

  const originInputLocked = locked || sourceInWorkspace;
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

  const statusLabel = running ? "Acquiring" : sourceInWorkspace ? "Ready" : "Empty";

  return (
    // Minimal form sitting directly on the focus dock — no nested frame/panel
    // layers. The dock supplies the floating surface over the canvas; the page
    // only paints its own content.
    <div style={pageRoot}>
      <GlassPageHeader
        icon={Ic.globe(24)}
        iconTint={{
          color: "#f59e0b",
          border: "rgba(245, 158, 11, 0.32)",
          shadow: "rgba(245, 158, 11, 0.14)",
        }}
        title="Source Acquisition"
        subtitle="Choose an acquisition path, load source into the workspace, then confirm snapshot behavior."
        badges={<span style={sourceBadge(sourceInWorkspace, running)}>{statusLabel}</span>}
        right={
          sourceInWorkspace ? (
            <button
              type="button"
              disabled={locked}
              onClick={() => {
                focus("sourceAvailable");
                onRemoveWorkspaceSource();
              }}
              style={clearSourceButton(locked)}
            >
              {Ic.x(13)} Clear source
            </button>
          ) : undefined
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SourceAcquisitionCard
          repoMode={repoMode}
          sourceConfigLocked={sourceConfigLocked}
          sourceInteractionLocked={sourceInteractionLocked}
          sourceInWorkspace={sourceInWorkspace}
          locked={locked}
          focusedField={focusedField}
          originUrlDraft={originUrlDraft}
          originTypeDraft={originTypeDraft}
          originInputLocked={originInputLocked}
          canDownload={canDownload}
          canUpload={canUpload}
          downloadRunning={downloadRunning}
          downloadDone={downloadDone}
          downloadLabel={downloadLabel}
          workspaceSourceState={workspaceSourceState}
          focus={focus}
          onRepoModeChange={onRepoModeChange}
          setOriginUrlDraft={setOriginUrlDraft}
          setOriginTypeDraft={setOriginTypeDraft}
          onDownloadSource={onDownloadSource}
          onCancelSource={onCancelSource}
          onWorkspaceUpload={onWorkspaceUpload}
        />

        <SourceStep3Section
          step3Ready={step3Ready}
          acquisitionNarrative={acquisitionNarrative}
          sourceMeta={sourceRepo}
        />

        <CollapsibleLogCard log={log} running={running} title="Acquisition log" />
      </div>
    </div>
  );
}

// The page is transparent so the dock surface reads through; generous top
// padding clears the dock's stage label and close button.
const pageRoot: React.CSSProperties = {
  height: "100%",
  minHeight: 0,
  overflow: "auto",
  padding: "46px 36px 32px",
  color: lgColors.text,
};

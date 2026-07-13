import type { SourceUploadCommit } from "@core/ree/ReeTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useEffect, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { useFocusScroll } from "../../shared/hooks/useFocusScroll";
import { lgColors, lgStatusBadge } from "../../theme/lightGlassTheme";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { isLikelySourceUrl } from "../components/sourceRuntime/SourceUrlField";
import type { AppShellPageContainerProps } from "../pages/pageContainers/shared";
import { useStepRunLogEntry } from "../pages/pageContainers/shared";
import type { SourceTypeOption } from "../pages/source/SourceAcquisitionPageHelpers";
import { SourceAcquisitionCard } from "../pages/source/SourceAcquisitionPageSections";
import { SourceStep3Section } from "../pages/source/SourceAcquisitionPageStep3Section";
import { CanvasWindowTitle } from "./CanvasWindow";
import { HubPanel } from "./HubPanel";

type SourceHubPanelProps = Pick<
  AppShellPageContainerProps,
  "ree" | "workspaceRemote" | "stepRuns" | "uiChrome" | "commands"
> & {
  onClose: () => void;
};

// Source acquisition is a short form (a URL + type, or a tarball upload), so it
// opens as a compact floating hub panel — like SBOM and the seal — instead of a
// full docked page.
export function SourceHubPanel({
  ree,
  workspaceRemote,
  stepRuns,
  uiChrome,
  commands,
  onClose,
}: SourceHubPanelProps) {
  const { reeId } = useApiRuntime();
  const { focusedField, locked, repoMode } = uiChrome;
  const { actionStates } = stepRuns;
  const { workspaceSourceState, sourceRepo } = workspaceRemote;

  const sourceLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.source,
    fallbackTimestamp: stepRuns.timestamps.source,
  });

  const [originTypeDraft, setOriginTypeDraft] = useState<SourceTypeOption | "">(
    ree.sourceType || "",
  );
  const [originUrlDraft, setOriginUrlDraft] = useState(ree.originUrl || "");
  // The requested revision — an acquisition input that pins the git fetch. It is
  // not persisted intent (that is ReeSpec.resolvedRevision, the commit it settles
  // to); it starts blank (HEAD) and is recorded afterward as the resolved commit.
  const [revisionDraft, setRevisionDraft] = useState("");

  useEffect(() => {
    setOriginTypeDraft(ree.sourceType || "");
  }, [ree.sourceType]);
  useEffect(() => {
    setOriginUrlDraft(ree.originUrl || "");
  }, [ree.originUrl]);
  // The revision draft has no persisted backing, so clear it when the source
  // leaves the workspace — otherwise a stale pin lingers into the next acquire.
  useEffect(() => {
    if (!workspaceSourceState.sourceAvailable) setRevisionDraft("");
  }, [workspaceSourceState.sourceAvailable]);

  useFocusScroll(focusedField);

  const focus = (key: string) => commands.setFocusedField(key);

  const running = actionStates.source === "loading";
  const downloadRunning = running;
  const sourceInWorkspace = !!workspaceSourceState.sourceAvailable;
  const sourceFromUpload = workspaceSourceState.sourceAcquiredBy === "upload" && sourceInWorkspace;
  const sourceFromDownload =
    workspaceSourceState.sourceAcquiredBy === "download" && sourceInWorkspace;
  const sourceConfigLocked = sourceInWorkspace;
  const sourceInteractionLocked = locked || sourceConfigLocked;
  const originInputLocked = locked || sourceInWorkspace;
  const step3Ready = sourceInWorkspace;
  const canDownload =
    isLikelySourceUrl(originUrlDraft) &&
    !!originTypeDraft &&
    repoMode === "url" &&
    !sourceInWorkspace;
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
    <HubPanel
      ariaLabel="Source Acquisition"
      onClose={onClose}
      width={520}
      header={
        <CanvasWindowTitle
          icon={Ic.globe(16)}
          iconColor="#f59e0b"
          title="Source Acquisition"
          subtitle="fetch or upload the source snapshot"
        />
      }
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={lgStatusBadge(sourceInWorkspace)}>{statusLabel}</span>
        <div style={{ flex: 1 }} />
        {sourceInWorkspace && (
          <button
            type="button"
            disabled={locked}
            onClick={() => {
              focus("sourceAvailable");
              commands.onRemoveWorkspaceSource();
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "5px 9px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
              border: "1px solid rgba(251, 113, 133, 0.4)",
              background: locked ? "rgba(241, 245, 249, 0.72)" : "rgba(255, 241, 242, 0.82)",
              color: locked ? lgColors.textMuted : lgColors.danger,
              cursor: locked ? "not-allowed" : "pointer",
              flexShrink: 0,
            }}
          >
            {Ic.x(12)} Clear source
          </button>
        )}
      </div>

      <SourceAcquisitionCard
        repoMode={repoMode}
        sourceConfigLocked={sourceConfigLocked}
        sourceInteractionLocked={sourceInteractionLocked}
        sourceInWorkspace={sourceInWorkspace}
        locked={locked}
        focusedField={focusedField}
        originUrlDraft={originUrlDraft}
        originTypeDraft={originTypeDraft}
        revisionDraft={revisionDraft}
        resolvedRevision={ree.resolvedRevision || ""}
        originInputLocked={originInputLocked}
        priorOriginUrl={ree.originUrl || ""}
        canDownload={canDownload}
        canUpload={canUpload}
        downloadRunning={downloadRunning}
        downloadDone={sourceFromDownload}
        downloadLabel={downloadLabel}
        workspaceSourceState={workspaceSourceState}
        focus={focus}
        onRepoModeChange={commands.setRepoMode}
        setOriginUrlDraft={setOriginUrlDraft}
        setOriginTypeDraft={setOriginTypeDraft}
        setRevisionDraft={setRevisionDraft}
        onDownloadSource={commands.onDownloadSourceFiles}
        onCancelSource={() => commands.onCancelAction("source")}
        onWorkspaceUpload={(payload: SourceUploadCommit) => commands.onWorkspaceUpload(payload)}
      />

      <SourceStep3Section
        step3Ready={step3Ready}
        acquisitionNarrative={acquisitionNarrative}
        sourceMeta={sourceRepo}
      />

      <CollapsibleLogCard log={sourceLog} running={running} title="Acquisition log" />
    </HubPanel>
  );
}

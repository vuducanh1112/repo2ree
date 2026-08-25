import type { SourceUploadCommit } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useReeId } from "@shell/data/apiRuntime";
import type { ReeEditorCommands } from "@shell/state/ree-editor/hooks/createReeEditorCommands";
import type { WorkspaceRemoteState } from "@shell/state/ree-editor/hooks/useReeEditor";
import { useStepRunLogEntry } from "@shell/state/ree-editor/step-runs/useStepRunLogEntry";
import type { StepRunState } from "@shell/state/ree-editor/store/stepRunState";
import type { UiChromeState } from "@shell/state/ree-editor/store/uiChrome";
import { useEffect, useState } from "react";
import { Badge } from "../../shared/components/Badge";
import { Button } from "../../shared/components/Button";
import { Ic } from "../../shared/components/Icon";
import { useFocusScroll } from "../../shared/hooks/useFocusScroll";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { isLikelySourceUrl } from "../components/sourceRuntime/SourceUrlField";
import type { SourceTypeOption } from "../pages/source/SourceAcquisitionPageHelpers";
import { SourceAcquisitionCard } from "../pages/source/SourceAcquisitionPageSections";
import { SourceStep3Section } from "../pages/source/SourceAcquisitionPageStep3Section";
import styles from "./SourceAcquisitionContent.module.css";

interface SourceAcquisitionContentProps {
  ree: ReeEditorViewModel;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  commands: Pick<
    ReeEditorCommands,
    | "setFocusedField"
    | "onRemoveWorkspaceSource"
    | "setRepoMode"
    | "onDownloadSourceFiles"
    | "onCancelAction"
    | "onWorkspaceUpload"
  >;
}

/** The source workflow page body, hosted by the shared workspace drawer. */
export function SourceAcquisitionContent({
  ree,
  workspaceRemote,
  stepRuns,
  uiChrome,
  commands,
}: SourceAcquisitionContentProps) {
  const reeId = useReeId();
  const { focusedField, locked, repoMode } = uiChrome;
  const { actionStates } = stepRuns;
  const { workspaceSourceState, sourceRepo } = workspaceRemote;

  const sourceLog = useStepRunLogEntry({
    reeId,
    runId: stepRuns.activeRunIds.source,
    fallbackTimestamp: stepRuns.timestamps.source,
  });

  const [originTypeDraft, setOriginTypeDraft] = useState<SourceTypeOption | "">(
    ree.spec.sourceType || "",
  );
  const [originUrlDraft, setOriginUrlDraft] = useState(ree.spec.originUrl || "");
  // The requested revision — an acquisition input that pins the git fetch. It is
  // not persisted intent (that is ReeSpec.resolvedRevision, the commit it settles
  // to); it starts blank (HEAD) and is recorded afterward as the resolved commit.
  const [revisionDraft, setRevisionDraft] = useState("");

  useEffect(() => {
    setOriginTypeDraft(ree.spec.sourceType || "");
  }, [ree.spec.sourceType]);
  useEffect(() => {
    setOriginUrlDraft(ree.spec.originUrl || "");
  }, [ree.spec.originUrl]);
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
    <div className={styles.page}>
      <div className={styles.statusBar}>
        <Badge tone={sourceInWorkspace ? "success" : "warning"}>{statusLabel}</Badge>
        <div className={styles.spacer} />
        {sourceInWorkspace && (
          <Button
            variant="danger"
            size="small"
            icon={Ic.x(12)}
            disabled={locked}
            onClick={() => {
              focus("sourceAvailable");
              commands.onRemoveWorkspaceSource();
            }}
          >
            Clear source
          </Button>
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
        resolvedRevision={ree.spec.resolvedRevision || ""}
        originInputLocked={originInputLocked}
        priorOriginUrl={ree.spec.originUrl || ""}
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
    </div>
  );
}

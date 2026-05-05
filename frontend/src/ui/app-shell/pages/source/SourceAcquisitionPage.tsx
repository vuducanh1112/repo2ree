import { useEffect, useState } from "react";
import { PAGE } from "../../../../application/state/pages";
import { Ic } from "../../../shared/components/Icon";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../theme/theme";
import { FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { WorkflowLogSection } from "../../components/workflowRunPanels";
import type { SourceAcquisitionPageProps } from "../sharedWorkflowUi";
import type { SourceTypeOption } from "./SourceAcquisitionPageHelpers";
import { SourceStep1Section, SourceStep2Section } from "./SourceAcquisitionPageSections";
import { SourceStep3Section } from "./SourceAcquisitionPageStep3Section";

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
  onWorkspaceSourceStateChange,
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
    onWorkspaceSourceStateChange((current) => ({
      ...current,
      sourceIncluded: !sourceIncluded,
    }));
  };

  useEffect(() => {
    if (!sourceInWorkspace && workspaceSourceState.sourceIncluded) {
      onWorkspaceSourceStateChange((current) => ({
        ...current,
        sourceIncluded: false,
      }));
    }
  }, [sourceInWorkspace, workspaceSourceState.sourceIncluded, onWorkspaceSourceStateChange]);

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
            <SourceStep1Section
              sourceConfigLocked={sourceConfigLocked}
              repoMode={repoMode}
              sourceInteractionLocked={sourceInteractionLocked}
              focus={focus}
              onRepoModeChange={onRepoModeChange}
              setOriginTypeDraft={setOriginTypeDraft}
              setOriginUrlDraft={setOriginUrlDraft}
            />
            <div style={{ marginTop: 12 }}>
              <SourceStep2Section
                repoMode={repoMode}
                sourceInWorkspace={sourceInWorkspace}
                locked={locked}
                sourceConfigLocked={sourceConfigLocked}
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
                setOriginUrlDraft={setOriginUrlDraft}
                setOriginTypeDraft={setOriginTypeDraft}
                onDownloadSource={onDownloadSource}
                onCancelSource={onCancelSource}
                onWorkspaceUpload={onWorkspaceUpload}
              />
            </div>
            <div style={{ marginTop: 12 }}>
              <SourceStep3Section
                step3Ready={step3Ready}
                sourceIncludedEffective={sourceIncludedEffective}
                sourceIncludedLocked={sourceIncludedLocked}
                sourceFromUpload={sourceFromUpload}
                sourceInWorkspace={sourceInWorkspace}
                acquisitionNarrative={acquisitionNarrative}
                workspaceSourceState={workspaceSourceState}
                locked={locked}
                focus={focus}
                onToggleSourceIncluded={toggleSourceIncluded}
                onGoWorkflow={onGoWorkflow}
                onRemoveWorkspaceSource={onRemoveWorkspaceSource}
              />
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

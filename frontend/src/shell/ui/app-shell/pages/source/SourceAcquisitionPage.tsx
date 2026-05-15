import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../../../shared/components/Icon";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  lgColors,
  lgNextButton,
  lgReadout,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { SummaryLine } from "../../components/SummaryLine";
import { PAGE } from "../../state/pages";
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

export function SourceAcquisitionPage({
  ree,
  inclusionState,
  workspaceSourceState,
  locked,
  repoMode,
  actionStates,
  log,
  running,
  focusedField,
  onWorkspaceSourceStateChange,
  onRepoModeChange,
  onGoAssemblyPage,
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
  const sourceIncluded = inclusionState.source === "included";
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

  const statusLabel = running ? "Acquiring" : sourceInWorkspace ? "Ready" : "Empty";
  const methodConfigured = repoMode === "upload" || (!!ree.origin_url && !!ree.source_type);
  const readinessDone = [methodConfigured, sourceInWorkspace].filter(Boolean).length;
  const readinessTotal = 2;
  const readinessPct = Math.round((readinessDone / readinessTotal) * 100);

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
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
        />

        <div style={lgStyles.mainGrid}>
          <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
            <div style={lgStyles.sectionBody}>
              <div style={lgStyles.sectionHeader}>
                <div
                  style={{
                    ...lgStyles.sectionIcon,
                    color: "#f59e0b",
                    border: "1px solid rgba(245, 158, 11, 0.28)",
                  }}
                >
                  {Ic.globe(19)}
                </div>
                <div>
                  <h2 style={lgStyles.sectionTitle}>Source Configuration</h2>
                  <div style={lgStyles.sectionSubtitle}>
                    Three steps: choose, acquire, confirm snapshot
                  </div>
                </div>
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
                sourceIncludedEffective={sourceIncludedEffective}
                sourceIncludedLocked={sourceIncludedLocked}
                sourceFromUpload={sourceFromUpload}
                sourceInWorkspace={sourceInWorkspace}
                acquisitionNarrative={acquisitionNarrative}
                workspaceSourceState={workspaceSourceState}
                locked={locked}
                focus={focus}
                onToggleSourceIncluded={toggleSourceIncluded}
                onGoAssemblyPage={onGoAssemblyPage}
                onRemoveWorkspaceSource={onRemoveWorkspaceSource}
              />

              <CollapsibleLogCard log={log} running={running} title="Acquisition log" />
            </div>

            <div style={lgStyles.footer}>
              <span style={{ color: lgColors.textMuted, fontSize: 12 }} />
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => onGoAssemblyPage(PAGE.METADATA)}
                  style={lgNextButton()}
                >
                  Next: Metadata {Ic.chevR(15)}
                </button>
              </div>
            </div>
          </section>

          <aside style={lgStyles.aside}>
            <section style={{ ...lgStyles.panel, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <span style={{ color: "#f59e0b", display: "flex" }}>{Ic.globe(22)}</span>
                <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Source Summary</h2>
              </div>

              <div style={lgStyles.summaryBox}>
                <div style={lgStyles.overviewHeader}>
                  <span style={lgStyles.overviewLabel}>Overview</span>
                  <span style={sourceBadge(sourceInWorkspace, running)}>{statusLabel}</span>
                </div>
                <SummaryLine
                  label="Method"
                  value={repoMode === "upload" ? "Upload tarball" : "Origin URL"}
                />
                <SummaryLine label="Origin URL" value={ree.origin_url || "Not set"} />
                <SummaryLine label="Origin type" value={ree.source_type || "Not set"} />
                <SummaryLine
                  label="Workspace"
                  value={sourceInWorkspace ? "Source loaded" : "No source"}
                />
                <SummaryLine
                  label="Acquired by"
                  value={workspaceSourceState.sourceAcquiredBy || "—"}
                />
                <SummaryLine
                  label="Include in REE"
                  value={sourceInWorkspace ? (sourceIncludedEffective ? "Yes" : "No") : "—"}
                />
              </div>
            </section>

            <section style={{ ...lgStyles.panel, padding: 16 }}>
              <div style={lgStyles.readinessHeader}>
                <span>Acquisition Readiness</span>
                <span style={{ color: lgColors.blue, fontFamily: F.mono }}>{readinessPct}%</span>
              </div>
              <div style={lgStyles.progressTrack}>
                <div
                  style={{
                    ...lgStyles.progressFill,
                    width: `${readinessPct}%`,
                  }}
                />
              </div>
              <div style={lgStyles.statGrid}>
                <div style={lgReadout(lgStyles.statReadout)}>
                  <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Required</span>
                  <strong style={{ color: lgColors.text, fontSize: 18 }}>
                    {readinessDone}/{readinessTotal}
                  </strong>
                </div>
                <div style={lgReadout(lgStyles.statReadout)}>
                  <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Source</span>
                  <strong style={{ color: lgColors.text, fontSize: 18 }}>
                    {sourceInWorkspace ? "✓" : "—"}
                  </strong>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

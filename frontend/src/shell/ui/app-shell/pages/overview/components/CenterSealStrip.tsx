import React from "react";
import type { InclusionOpts } from "../../../../../../core/ree/InclusionOpts";
import type { Badges, LogEntry } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { CollapsibleLogCard } from "../../../components/CollapsibleLogCard";
import { buildSealCableItems } from "./CenterSealStrip/helpers";
import { SealConfirmModal } from "./CenterSealStrip/SealConfirmModal";
import { SealedSealCard } from "./CenterSealStrip/SealedSealCard";
import { SealStatusCard } from "./CenterSealStrip/SealStatusCard";

interface CenterSealStripProps {
  ree: ReeEditorViewModel;
  locked: boolean;
  evaluation: EvaluationState;
  badges: Badges;
  onSeal: (inclusionOpts: InclusionOpts) => void;
  sealRunning?: boolean;
  sealLog?: LogEntry | null;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
  onReleaseWorkbench?: () => void;
  sealRef: React.RefObject<HTMLDivElement>;
}

export function CenterSealStrip({
  ree,
  locked,
  evaluation,
  badges,
  onSeal,
  sealRunning = false,
  sealLog = null,
  onPreviewReviewer,
  onDownloadRee,
  onReleaseWorkbench,
  sealRef,
}: CenterSealStripProps) {
  const [showSealConfirm, setShowSealConfirm] = React.useState(false);
  const sourceAvailable = !!ree.sourceAvailable;
  const runtimeAvailable = !!ree.runtime?.trim() && ree.runtime !== "__skipped__";
  const [includeSource, setIncludeSource] = React.useState(sourceAvailable);
  const [includeRuntime, setIncludeRuntime] = React.useState(runtimeAvailable);

  // Default the seal-time choices to whatever is available; the user can opt out
  // in the confirmation window. Availability can change while authoring, so keep
  // the defaults in step until the user has actually opened the window.
  React.useEffect(() => {
    if (!showSealConfirm) {
      setIncludeSource(sourceAvailable);
      setIncludeRuntime(runtimeAvailable);
    }
  }, [showSealConfirm, sourceAvailable, runtimeAvailable]);

  const sealed = locked && ree.sealedAt;
  const cableItems = buildSealCableItems(ree, badges);
  const liveCount = cableItems.filter((item) => item.live).length;
  const totalCables = cableItems.length;
  const allLive = liveCount === totalCables;
  const missing = cableItems.filter((item) => !item.live);
  const currentLevelMeta = standingMeta(evaluation);

  const logPanel = (
    <div style={{ width: "100%", maxWidth: 480 }}>
      <CollapsibleLogCard log={sealLog} running={sealRunning} title="Seal log" />
    </div>
  );

  if (sealed) {
    return (
      <>
        <SealedSealCard
          ree={ree}
          onPreviewReviewer={onPreviewReviewer}
          onDownloadRee={onDownloadRee}
          onReleaseWorkbench={onReleaseWorkbench}
          sealRef={sealRef}
          cableItems={cableItems}
          currentLevelMeta={currentLevelMeta}
        />
        {logPanel}
      </>
    );
  }

  return (
    <>
      <SealConfirmModal
        open={showSealConfirm}
        onClose={() => setShowSealConfirm(false)}
        onConfirm={() => {
          setShowSealConfirm(false);
          onSeal({
            includeSource: sourceAvailable && includeSource,
            includeRuntime: runtimeAvailable && includeRuntime,
          });
        }}
        missing={missing}
        allLive={allLive}
        totalCables={totalCables}
        currentLevelMeta={currentLevelMeta}
        sourceAvailable={sourceAvailable}
        runtimeAvailable={runtimeAvailable}
        includeSource={includeSource}
        includeRuntime={includeRuntime}
        onToggleSource={() => setIncludeSource((v) => !v)}
        onToggleRuntime={() => setIncludeRuntime((v) => !v)}
      />

      <SealStatusCard
        sealRef={sealRef}
        currentLevelMeta={currentLevelMeta}
        cableItems={cableItems}
        allLive={allLive}
        missing={missing}
        sealRunning={sealRunning}
        onShowConfirm={() => setShowSealConfirm(true)}
      />
      {logPanel}
    </>
  );
}

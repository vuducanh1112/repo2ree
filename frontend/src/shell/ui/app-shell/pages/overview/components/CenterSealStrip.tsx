import React from "react";
import type { Badges } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { buildSealCableItems } from "./CenterSealStrip/helpers";
import { SealConfirmModal } from "./CenterSealStrip/SealConfirmModal";
import { SealedSealCard } from "./CenterSealStrip/SealedSealCard";
import { SealStatusCard } from "./CenterSealStrip/SealStatusCard";

interface CenterSealStripProps {
  ree: ReeEditorViewModel;
  locked: boolean;
  evaluation: EvaluationState;
  badges: Badges;
  onSeal: () => void;
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
  onPreviewReviewer,
  onDownloadRee,
  onReleaseWorkbench,
  sealRef,
}: CenterSealStripProps) {
  const [showSealConfirm, setShowSealConfirm] = React.useState(false);
  const sealed = locked && ree.sealedAt;
  const cableItems = buildSealCableItems(ree, badges);
  const liveCount = cableItems.filter((item) => item.live).length;
  const totalCables = cableItems.length;
  const allLive = liveCount === totalCables;
  const missing = cableItems.filter((item) => !item.live);
  const currentLevelMeta = standingMeta(evaluation);

  if (sealed) {
    return (
      <SealedSealCard
        ree={ree}
        onPreviewReviewer={onPreviewReviewer}
        onDownloadRee={onDownloadRee}
        onReleaseWorkbench={onReleaseWorkbench}
        sealRef={sealRef}
        cableItems={cableItems}
        currentLevelMeta={currentLevelMeta}
      />
    );
  }

  return (
    <>
      <SealConfirmModal
        open={showSealConfirm}
        onClose={() => setShowSealConfirm(false)}
        onConfirm={() => {
          setShowSealConfirm(false);
          onSeal?.();
        }}
        missing={missing}
        allLive={allLive}
        totalCables={totalCables}
        currentLevelMeta={currentLevelMeta}
      />

      <SealStatusCard
        sealRef={sealRef}
        currentLevelMeta={currentLevelMeta}
        cableItems={cableItems}
        allLive={allLive}
        missing={missing}
        onShowConfirm={() => setShowSealConfirm(true)}
      />
    </>
  );
}

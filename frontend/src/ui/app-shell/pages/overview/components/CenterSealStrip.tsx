import React from "react";
import type { Badges } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import { LEVELS } from "../../../../../core/review/levels";
import { buildSealCableItems } from "./CenterSealStrip/helpers";
import { SealConfirmModal } from "./CenterSealStrip/SealConfirmModal";
import { SealedSealCard } from "./CenterSealStrip/SealedSealCard";
import { SealStatusCard } from "./CenterSealStrip/SealStatusCard";

interface CenterSealStripProps {
  ree: ReeEditorViewModel;
  locked: boolean;
  level: number;
  badges: Badges;
  onSeal: () => void;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
  sealRef: React.RefObject<HTMLDivElement>;
}

export function CenterSealStrip({
  ree,
  locked,
  level,
  badges,
  onSeal,
  onPreviewReviewer,
  onDownloadRee,
  sealRef,
}: CenterSealStripProps) {
  const [showSealConfirm, setShowSealConfirm] = React.useState(false);
  const sealed = locked && ree.sealedAt;
  const cableItems = buildSealCableItems(ree, badges);
  const liveCount = cableItems.filter((item) => item.live).length;
  const totalCables = cableItems.length;
  const allLive = liveCount === totalCables;
  const missing = cableItems.filter((item) => !item.live);
  const currentLevelMeta = LEVELS[Math.min(level, 7)];

  if (sealed) {
    return (
      <SealedSealCard
        ree={ree}
        level={level}
        onPreviewReviewer={onPreviewReviewer}
        onDownloadRee={onDownloadRee}
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
        level={level}
        totalCables={totalCables}
        currentLevelMeta={currentLevelMeta}
      />

      <SealStatusCard
        sealRef={sealRef}
        level={level}
        currentLevelMeta={currentLevelMeta}
        cableItems={cableItems}
        allLive={allLive}
        missing={missing}
        onShowConfirm={() => setShowSealConfirm(true)}
      />
    </>
  );
}

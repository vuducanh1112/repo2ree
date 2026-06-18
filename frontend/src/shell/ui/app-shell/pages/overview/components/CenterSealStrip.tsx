import React from "react";
import type { InclusionOpts } from "../../../../../../core/ree/InclusionOpts";
import type { Badges, LogEntry } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { CollapsibleLogCard } from "../../../components/CollapsibleLogCard";
import { buildSealCableItems } from "./CenterSealStrip/helpers";
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
  sealRef,
}: CenterSealStripProps) {
  const sourceAvailable = !!ree.sourceAvailable;
  const runtimeAvailable = !!ree.runtime?.trim() && ree.runtime !== "__skipped__";
  const [includeSource, setIncludeSource] = React.useState(sourceAvailable);
  const [includeRuntime, setIncludeRuntime] = React.useState(runtimeAvailable);

  // Default the seal-time choices to whatever is available; the user can opt out
  // inline before sealing. Availability can change while authoring, so keep the
  // defaults in step with what the workspace actually has.
  React.useEffect(() => {
    setIncludeSource(sourceAvailable);
    setIncludeRuntime(runtimeAvailable);
  }, [sourceAvailable, runtimeAvailable]);

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
      <SealStatusCard
        sealRef={sealRef}
        currentLevelMeta={currentLevelMeta}
        cableItems={cableItems}
        allLive={allLive}
        totalCables={totalCables}
        missing={missing}
        sealRunning={sealRunning}
        sourceAvailable={sourceAvailable}
        runtimeAvailable={runtimeAvailable}
        includeSource={includeSource}
        includeRuntime={includeRuntime}
        onToggleSource={() => setIncludeSource((v) => !v)}
        onToggleRuntime={() => setIncludeRuntime((v) => !v)}
        onSeal={() =>
          onSeal({
            includeSource: sourceAvailable && includeSource,
            includeRuntime: runtimeAvailable && includeRuntime,
          })
        }
      />
      {logPanel}
    </>
  );
}

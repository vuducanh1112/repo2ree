import { buildSealCableItems } from "@core/canvas/sealCableScene";
import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { LogEntry } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { CollapsibleLogCard } from "@shell/ui/app-shell/components/CollapsibleLogCard";
import React from "react";
import styles from "./CenterSealStrip/CenterSealStrip.module.css";
import { SealedSealCard } from "./CenterSealStrip/SealedSealCard";
import { SealStatusCard } from "./CenterSealStrip/SealStatusCard";

interface CenterSealStripProps {
  ree: ReeEditorViewModel;
  locked: boolean;
  onSeal: (inclusionOpts: InclusionOpts) => void;
  sealRunning?: boolean;
  sealLog?: LogEntry | null;
  sealRef: React.RefObject<HTMLDivElement>;
}

export function CenterSealStrip({
  ree,
  locked,
  onSeal,
  sealRunning = false,
  sealLog = null,
  sealRef,
}: CenterSealStripProps) {
  const sourceAvailable = !!ree.source.sourceAvailable;
  const runtimeAvailable = !!ree.spec.runtime?.trim() && ree.spec.runtime !== "__skipped__";
  // Results are available to seal once any experiment declares an output — those
  // are what a successful run captures into the produced-results store.
  const resultsAvailable = (ree.spec.experiments ?? []).some((e) => e.outputPaths.length > 0);
  const [includeSource, setIncludeSource] = React.useState(sourceAvailable);
  const [includeRuntime, setIncludeRuntime] = React.useState(runtimeAvailable);
  const [includeResults, setIncludeResults] = React.useState(resultsAvailable);

  // Default the seal-time choices to whatever is available; the user can opt out
  // inline before sealing. Availability can change while authoring, so keep the
  // defaults in step with what the workspace actually has.
  React.useEffect(() => {
    setIncludeSource(sourceAvailable);
    setIncludeRuntime(runtimeAvailable);
    setIncludeResults(resultsAvailable);
  }, [sourceAvailable, runtimeAvailable, resultsAvailable]);

  const sealed = locked && ree.artifact.sealedAt;
  const cableItems = buildSealCableItems(ree);
  const liveCount = cableItems.filter((item) => item.live).length;
  const totalCables = cableItems.length;
  const allLive = liveCount === totalCables;
  const missing = cableItems.filter((item) => !item.live);
  const currentLevelMeta = {
    color: "var(--seal-level-line)",
    bg: "var(--seal-level-wash)",
    label: "REE evidence",
  };

  const logPanel = (
    <div className={styles.strip}>
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
        resultsAvailable={resultsAvailable}
        includeSource={includeSource}
        includeRuntime={includeRuntime}
        includeResults={includeResults}
        onToggleSource={() => setIncludeSource((v) => !v)}
        onToggleRuntime={() => setIncludeRuntime((v) => !v)}
        onToggleResults={() => setIncludeResults((v) => !v)}
        onSeal={() =>
          onSeal({
            includeSource: sourceAvailable && includeSource,
            includeRuntime: runtimeAvailable && includeRuntime,
            includeResults: resultsAvailable && includeResults,
          })
        }
      />
      {logPanel}
    </>
  );
}

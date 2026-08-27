import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { Badges, LogEntry } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useRef } from "react";
import { CenterSealStrip } from "./CenterSealStrip";
import styles from "./SealContent.module.css";

interface SealContentProps {
  ree: ReeEditorViewModel;
  badges: Badges;
  locked: boolean;
  sealRunning: boolean;
  sealLog: LogEntry | null;
  onSeal: (inclusionOpts: InclusionOpts) => void;
}

/** The sealing workflow body, hosted by the shared workspace drawer. */
export function SealContent({
  ree,
  badges,
  locked,
  sealRunning,
  sealLog,
  onSeal,
}: SealContentProps) {
  const sealRef = useRef<HTMLDivElement>(null);

  return (
    <div className={styles.page}>
      <CenterSealStrip
        ree={ree}
        badges={badges}
        locked={locked}
        onSeal={onSeal}
        sealRunning={sealRunning}
        sealLog={sealLog}
        sealRef={sealRef}
      />
    </div>
  );
}

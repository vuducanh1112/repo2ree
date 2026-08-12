import type { SealCableItem } from "@core/canvas/sealCableScene";
import { Ic } from "@shell/ui/shared/components/Icon";
import { cssVars } from "@shell/ui/theme/styleVars";
import type React from "react";
import styles from "./CenterSealStrip.module.css";
import { SealConfirmCopy } from "./SealConfirmCopy";
import { SealConfirmInclusion } from "./SealConfirmInclusion";
import { SealConfirmWarning } from "./SealConfirmWarning";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealStatusCardProps {
  sealRef: React.RefObject<HTMLDivElement>;
  currentLevelMeta: LevelMeta;
  cableItems: SealCableItem[];
  allLive: boolean;
  totalCables: number;
  missing: { key: string; label: string }[];
  sealRunning?: boolean;
  sourceAvailable: boolean;
  runtimeAvailable: boolean;
  resultsAvailable: boolean;
  includeSource: boolean;
  includeRuntime: boolean;
  includeResults: boolean;
  onToggleSource: () => void;
  onToggleRuntime: () => void;
  onToggleResults: () => void;
  onSeal: () => void;
}

export function SealStatusCard({
  sealRef,
  currentLevelMeta,
  cableItems,
  allLive,
  totalCables,
  missing,
  sealRunning = false,
  sourceAvailable,
  runtimeAvailable,
  resultsAvailable,
  includeSource,
  includeRuntime,
  includeResults,
  onToggleSource,
  onToggleRuntime,
  onToggleResults,
  onSeal,
}: SealStatusCardProps) {
  const liveCount = cableItems.filter((item) => item.live).length;
  return (
    <div
      ref={sealRef}
      className={styles.panel}
      style={cssVars({ "--seal-tint": currentLevelMeta.color })}
    >
      <div className={styles.bar}>
        <span className={styles.count}>
          {liveCount}/{cableItems.length} connected
        </span>
        <div className={styles.track}>
          {cableItems.map((item) => (
            <div
              key={item.label}
              title={item.label}
              className={styles.segment}
              data-live={item.live || undefined}
            />
          ))}
        </div>
        <span className={styles.readiness} data-ready={allLive || undefined}>
          {allLive ? "ready" : "incomplete"}
        </span>
      </div>

      {!allLive && <SealConfirmWarning missing={missing} />}

      <SealConfirmCopy
        allLive={allLive}
        totalCables={totalCables}
        currentLabel={currentLevelMeta.label}
      />

      <SealConfirmInclusion
        sourceAvailable={sourceAvailable}
        runtimeAvailable={runtimeAvailable}
        resultsAvailable={resultsAvailable}
        includeSource={includeSource}
        includeRuntime={includeRuntime}
        includeResults={includeResults}
        onToggleSource={onToggleSource}
        onToggleRuntime={onToggleRuntime}
        onToggleResults={onToggleResults}
      />

      <div className={styles.actions}>
        <button
          type="button"
          onClick={onSeal}
          disabled={sealRunning}
          aria-busy={sealRunning || undefined}
          className={styles.seal}
        >
          <span aria-hidden className={styles.sealIcon}>
            {sealRunning ? Ic.loader(13) : Ic.lock(13)}
          </span>
          {sealRunning ? "Sealing…" : allLive ? "Seal REE" : "Seal anyway"}
        </button>
      </div>
    </div>
  );
}

import type { StaleSealItem } from "@core/ree-assembly/sealConsistency";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgBackgrounds, lgColors, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F, hoverBrightness, S_ACTION_BUTTON_BASE } from "@shell/ui/theme/theme";
import type React from "react";
import type { SealCableItem } from "./helpers";
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
  stale?: StaleSealItem[];
  sealRunning?: boolean;
  sourceAvailable: boolean;
  runtimeAvailable: boolean;
  includeSource: boolean;
  includeRuntime: boolean;
  onToggleSource: () => void;
  onToggleRuntime: () => void;
  onSeal: () => void;
}

export function SealStatusCard({
  sealRef,
  currentLevelMeta,
  cableItems,
  allLive,
  totalCables,
  missing,
  stale = [],
  sealRunning = false,
  sourceAvailable,
  runtimeAvailable,
  includeSource,
  includeRuntime,
  onToggleSource,
  onToggleRuntime,
  onSeal,
}: SealStatusCardProps) {
  const liveCount = cableItems.filter((item) => item.live).length;
  return (
    <div ref={sealRef} style={{ ...lgStyles.overviewPanel, width: "100%", maxWidth: 480 }}>
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid rgba(148, 163, 184, 0.24)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          background: lgBackgrounds.glassStrong,
        }}
      >
        <span
          style={{ fontSize: 10, fontFamily: F.mono, color: lgColors.textMuted, flexShrink: 0 }}
        >
          {liveCount}/{cableItems.length} connected
        </span>
        <div style={{ flex: 1, display: "flex", gap: 3, alignItems: "center" }}>
          {cableItems.map((item) => (
            <div
              key={item.label}
              title={item.label}
              style={{
                flex: 1,
                height: 3,
                borderRadius: 99,
                background: item.live ? currentLevelMeta.color : "rgba(148, 163, 184, 0.4)",
                transition: "background 0.3s",
              }}
            />
          ))}
        </div>
        {allLive ? (
          <span
            style={{
              fontSize: 10,
              fontFamily: F.mono,
              fontWeight: 700,
              borderRadius: 99,
              padding: "2px 8px",
              letterSpacing: 0.5,
              flexShrink: 0,
              color: currentLevelMeta.color,
              background: `${currentLevelMeta.color}14`,
              border: `1px solid ${currentLevelMeta.color}40`,
            }}
          >
            ready
          </span>
        ) : (
          <span
            style={{
              fontSize: 10,
              fontFamily: F.mono,
              fontWeight: 700,
              borderRadius: 99,
              padding: "2px 8px",
              letterSpacing: 0.5,
              flexShrink: 0,
              color: lgColors.warning,
              background: lgBackgrounds.draft,
              border: "1px solid rgba(245, 158, 11, 0.45)",
            }}
          >
            incomplete
          </span>
        )}
      </div>

      {(!allLive || stale.length > 0) && <SealConfirmWarning missing={missing} stale={stale} />}

      <SealConfirmCopy
        allLive={allLive}
        totalCables={totalCables}
        currentLabel={currentLevelMeta.label}
      />

      <SealConfirmInclusion
        sourceAvailable={sourceAvailable}
        runtimeAvailable={runtimeAvailable}
        includeSource={includeSource}
        includeRuntime={includeRuntime}
        onToggleSource={onToggleSource}
        onToggleRuntime={onToggleRuntime}
      />

      <div style={{ padding: "12px 14px", display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onSeal}
          disabled={sealRunning}
          style={{
            ...S_ACTION_BUTTON_BASE,
            display: "flex",
            alignItems: "center",
            gap: 7,
            padding: "9px 18px",
            borderRadius: 8,
            flexShrink: 0,
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: 0.3,
            cursor: sealRunning ? "not-allowed" : "pointer",
            color: lgColors.white,
            background: currentLevelMeta.color,
            border: `1px solid ${currentLevelMeta.color}`,
            boxShadow: `0 12px 24px ${currentLevelMeta.color}40`,
            opacity: sealRunning ? 0.7 : 1,
          }}
          {...(sealRunning ? {} : hoverBrightness(92))}
        >
          <span
            style={{
              display: "flex",
              animation: sealRunning ? "spin 0.9s linear infinite" : "none",
            }}
          >
            {sealRunning ? Ic.loader(13) : Ic.lock(13)}
          </span>
          {sealRunning ? "Sealing…" : allLive ? "Seal REE" : "Seal anyway"}
        </button>
      </div>
    </div>
  );
}

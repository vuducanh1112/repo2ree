import type React from "react";
import { Ic } from "../../../../../shared/components/Icon";
import { lgBackgrounds, lgColors, lgStyles } from "../../../../../theme/lightGlassTheme";
import { F, hoverBrightness, S_ACTION_BUTTON_BASE } from "../../../../../theme/theme";
import type { SealCableItem } from "./helpers";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealStatusCardProps {
  sealRef: React.RefObject<HTMLDivElement>;
  level: number;
  currentLevelMeta: LevelMeta;
  cableItems: SealCableItem[];
  allLive: boolean;
  missing: { key: string; label: string }[];
  onShowConfirm: () => void;
}

export function SealStatusCard({
  sealRef,
  level,
  currentLevelMeta,
  cableItems,
  allLive,
  missing,
  onShowConfirm,
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
      <div style={{ padding: "12px 14px", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontFamily: F.sans, fontWeight: 800, color: lgColors.text }}>
            Seal REE
          </div>
          <div
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              marginTop: 2,
              color: allLive ? lgColors.textMuted : lgColors.warning,
            }}
          >
            {allLive
              ? `L${level} · ${currentLevelMeta.label} — all panels connected`
              : `${missing.length} panel${missing.length !== 1 ? "s" : ""} not yet connected`}
          </div>
        </div>
        <button
          type="button"
          onClick={onShowConfirm}
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
            cursor: "pointer",
            color: lgColors.white,
            background: currentLevelMeta.color,
            border: `1px solid ${currentLevelMeta.color}`,
            boxShadow: `0 12px 24px ${currentLevelMeta.color}40`,
          }}
          {...hoverBrightness(92)}
        >
          <span style={{ display: "flex" }}>{Ic.lock(13)}</span>
          Seal
        </button>
      </div>
    </div>
  );
}

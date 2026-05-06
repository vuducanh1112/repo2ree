import type React from "react";
import { Ic } from "../../../../../shared/components/Icon";
import {
  C,
  F,
  hoverBrightness,
  S_ACTION_BUTTON_BASE,
  S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
} from "../../../../../theme/theme";
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
  return (
    <div
      ref={sealRef}
      style={{
        width: "100%",
        maxWidth: 480,
        background: C.surface,
        border: `1.5px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "9px 14px",
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontFamily: F.mono,
            color: C.textMuted,
            flexShrink: 0,
          }}
        >
          {cableItems.filter((item) => item.live).length}/{cableItems.length} connected
        </span>
        <div
          style={{
            flex: 1,
            display: "flex",
            gap: 3,
            alignItems: "center",
          }}
        >
          {cableItems.map((item) => (
            <div
              key={item.label}
              title={item.label}
              style={{
                flex: 1,
                height: 3,
                borderRadius: 99,
                background: item.live ? currentLevelMeta.color : C.border,
                transition: "background 0.3s",
              }}
            />
          ))}
        </div>
        {allLive ? (
          <span
            style={{
              ...S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
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
              ...S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
              color: "#d97706",
              background: "#fffbeb",
              border: "1px solid #fde68a",
            }}
          >
            incomplete
          </span>
        )}
      </div>
      <div
        style={{
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            flex: 1,
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontFamily: F.mono,
              fontWeight: 600,
              color: C.text,
            }}
          >
            Seal REE
          </div>
          <div
            style={{
              ...{
                fontSize: 10,
                fontFamily: F.mono,
                marginTop: 2,
              },
              color: allLive ? C.textMuted : "#d97706",
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
            ...{
              ...S_ACTION_BUTTON_BASE,
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 18px",
              borderRadius: 7,
              flexShrink: 0,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 0.3,
              cursor: "pointer",
              color: "#fff",
              transition: "all 0.2s",
            },
            background: currentLevelMeta.color,
            border: `1.5px solid ${currentLevelMeta.color}`,
            boxShadow: `0 2px 10px ${currentLevelMeta.color}50`,
          }}
          {...hoverBrightness(92)}
        >
          <span
            style={{
              display: "flex",
            }}
          >
            {Ic.lock(13)}
          </span>
          Seal
        </button>
      </div>
    </div>
  );
}

import type { SealCableItem } from "@core/canvas/sealCableScene";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors } from "@shell/ui/theme/lightGlassTheme";
import { F, S_SEALED_META_KEY, S_SEALED_META_ROW } from "@shell/ui/theme/theme";
import type React from "react";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealedSealCardProps {
  ree: ReeEditorViewModel;
  sealRef: React.RefObject<HTMLDivElement>;
  cableItems: SealCableItem[];
  currentLevelMeta: LevelMeta;
}

export function SealedSealCard({
  ree,
  sealRef,
  cableItems,
  currentLevelMeta,
}: SealedSealCardProps) {
  const sealDate = new Date(ree.sealedAt ?? new Date().toISOString()).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      ref={sealRef}
      style={{
        width: "100%",
        maxWidth: 480,
        borderRadius: 12,
        overflow: "hidden",
        background: "rgba(255, 255, 255, 0.62)",
        backdropFilter: "blur(14px)",
        border: `1px solid ${currentLevelMeta.color}50`,
        boxShadow: `0 0 0 3px ${currentLevelMeta.color}14, 0 12px 32px rgba(15, 23, 42, 0.1)`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          borderBottom: `1px solid ${currentLevelMeta.color}30`,
          background: `${currentLevelMeta.color}10`,
        }}
      >
        <span style={{ display: "flex", flexShrink: 0, color: currentLevelMeta.color }}>
          {Ic.lock(13)}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            fontFamily: F.sans,
            letterSpacing: 0.4,
            color: currentLevelMeta.color,
          }}
        >
          REE SEALED
        </span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 9,
            fontFamily: F.mono,
            borderRadius: 99,
            padding: "2px 7px",
            letterSpacing: 0.6,
            fontWeight: 700,
            color: currentLevelMeta.color,
            background: `${currentLevelMeta.color}18`,
            border: `1px solid ${currentLevelMeta.color}40`,
          }}
        >
          {currentLevelMeta.label}
        </span>
      </div>
      <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={S_SEALED_META_ROW}>
          <span style={S_SEALED_META_KEY}>hash</span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: lgColors.text,
              fontWeight: 600,
              letterSpacing: 0.8,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {ree.sealHash || "—"}
          </span>
        </div>
        <div style={S_SEALED_META_ROW}>
          <span style={S_SEALED_META_KEY}>sealed</span>
          <span style={{ fontFamily: F.mono, fontSize: 10, color: lgColors.textMid }}>
            {sealDate}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 3, marginTop: 2 }}>
          {cableItems.map((item) => (
            <div
              key={item.label}
              title={item.label}
              style={{
                flex: 1,
                height: 3,
                borderRadius: 99,
                background: item.live ? currentLevelMeta.color : "rgba(148, 163, 184, 0.45)",
                opacity: item.live ? 0.85 : 0.5,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

import type React from "react";
import type { ReeEditorViewModel } from "../../../../../../application/ree-editor/reeEditorViewModel";
import { Ic } from "../../../../../shared/components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  S_OVERVIEW_SEALED_ACTION_BTN_BASE,
  S_OVERVIEW_SEALED_META_KEY,
  S_OVERVIEW_SEALED_META_ROW,
} from "../../../../../theme/theme";
import type { SealCableItem } from "./helpers";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealedSealCardProps {
  ree: ReeEditorViewModel;
  level: number;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
  sealRef: React.RefObject<HTMLDivElement>;
  cableItems: SealCableItem[];
  currentLevelMeta: LevelMeta;
}

export function SealedSealCard({
  ree,
  level,
  onPreviewReviewer,
  onDownloadRee,
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
        ...{
          width: "100%",
          maxWidth: 480,
          background: C.surface,
          borderRadius: 10,
          overflow: "hidden",
        },
        border: `1.5px solid ${currentLevelMeta.color}50`,
        boxShadow: `0 0 0 3px ${currentLevelMeta.color}14, 0 2px 12px rgba(0,0,0,0.07)`,
      }}
    >
      <div
        style={{
          ...{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 14px",
          },
          borderBottom: `1px solid ${currentLevelMeta.color}30`,
          background: `${currentLevelMeta.color}0c`,
        }}
      >
        <span
          style={{
            ...{
              display: "flex",
              flexShrink: 0,
            },
            color: currentLevelMeta.color,
          }}
        >
          {Ic.lock(13)}
        </span>
        <span
          style={{
            ...{
              fontSize: 11,
              fontWeight: 700,
              fontFamily: F.sans,
              letterSpacing: 0.4,
            },
            color: currentLevelMeta.color,
          }}
        >
          REE SEALED
        </span>
        <span
          style={{
            ...{
              marginLeft: "auto",
              fontSize: 9,
              fontFamily: F.mono,
              borderRadius: 3,
              padding: "1px 6px",
              letterSpacing: 0.6,
              fontWeight: 700,
            },
            color: currentLevelMeta.color,
            background: `${currentLevelMeta.color}18`,
            border: `1px solid ${currentLevelMeta.color}40`,
          }}
        >
          L{level} · {currentLevelMeta.label}
        </span>
      </div>
      <div
        style={{
          padding: "10px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={S_OVERVIEW_SEALED_META_ROW}>
          <span style={S_OVERVIEW_SEALED_META_KEY}>hash</span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: C.text,
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
        <div style={S_OVERVIEW_SEALED_META_ROW}>
          <span style={S_OVERVIEW_SEALED_META_KEY}>sealed</span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 10,
              color: C.textMid,
            }}
          >
            {sealDate}
          </span>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 3,
            marginTop: 2,
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
                background: item.live ? currentLevelMeta.color : "#d1d5db",
                opacity: item.live ? 0.85 : 0.4,
              }}
            />
          ))}
        </div>
        {onPreviewReviewer && (
          <button
            type="button"
            onClick={onPreviewReviewer}
            style={{
              ...S_OVERVIEW_SEALED_ACTION_BTN_BASE,
              background: `linear-gradient(135deg, ${currentLevelMeta.color}18 0%, ${currentLevelMeta.color}0c 100%)`,
              border: `1.5px solid ${currentLevelMeta.color}50`,
              color: currentLevelMeta.color,
            }}
            {...hoverBg(
              `${currentLevelMeta.color}28`,
              `linear-gradient(135deg, ${currentLevelMeta.color}18 0%, ${currentLevelMeta.color}0c 100%)`,
            )}
            {...hoverBorderColor(`${currentLevelMeta.color}80`, `${currentLevelMeta.color}50`)}
          >
            {Ic.star(12)}
            Preview Review
          </button>
        )}
        {onDownloadRee && (
          <button
            type="button"
            onClick={onDownloadRee}
            style={{
              ...S_OVERVIEW_SEALED_ACTION_BTN_BASE,
              background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
              border: "1.5px solid #86efac",
              color: "#15803d",
            }}
            {...hoverBg("#bbf7d0", "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)")}
            {...hoverBorderColor("#4ade80", "#86efac")}
          >
            {Ic.download(12)}
            Download REE
          </button>
        )}
      </div>
    </div>
  );
}

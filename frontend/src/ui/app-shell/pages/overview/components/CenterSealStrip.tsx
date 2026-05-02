import React from "react";
import { PAGE } from "../../../../../application/app-shell/AppShellPages";
import { hbomHasAnyComponents } from "../../../../../domain/hbom/HbomSummary";
import type { ReeDraftViewModel } from "../../../../../domain/ree/ReeSpec";
import type { Badges } from "../../../../../domain/ree/ReeTypes";
import { LEVELS } from "../../../../../domain/review/levels";
import { Ic } from "../../../../shared/components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverBrightness,
  S_ACTION_BUTTON_BASE,
  S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
  S_OVERVIEW_SEALED_ACTION_BTN_BASE,
  S_OVERVIEW_SEALED_META_KEY,
  S_OVERVIEW_SEALED_META_ROW,
} from "../../../../theme/theme";

interface CenterSealStripProps {
  ree: ReeDraftViewModel;
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
  const cableItems = [
    {
      key: PAGE.METADATA,
      label: "Metadata",
      live: !!ree.name,
    },
    {
      key: PAGE.HBOM,
      label: "HBOM",
      live: hbomHasAnyComponents(ree.hardware_description),
    },
    { key: PAGE.SOURCE, label: "Source", live: !!ree.sourceAvailable },
    { key: "runtime", label: "Runtime", live: !!ree.runtimeIncluded },
    { key: "swh", label: "Software Heritage", live: !!ree.swhid },
    { key: "sbom", label: "SBOM", live: !!ree.sbom },
    { key: "evaluate", label: "Evaluate", live: !!badges?.evaluate },
    {
      key: "archive",
      label: "Archival & DOIs",
      live: !!(ree.zenodo_doi || ree.dataverse_doi),
    },
    {
      key: "activation",
      label: "Test Activation",
      live: !!badges?.activation,
    },
  ];
  const liveCount = cableItems.filter((item) => item.live).length;
  const totalCables = cableItems.length;
  const allLive = liveCount === totalCables;
  const missing = cableItems.filter((item) => !item.live);
  const currentLevelMeta = LEVELS[Math.min(level, 7)];

  if (sealed) {
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

  return (
    <>
      {showSealConfirm && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(0,0,0,0.45)",
            backdropFilter: "blur(3px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <button
            type="button"
            aria-label="Close confirmation"
            onClick={() => setShowSealConfirm(false)}
            style={{
              position: "absolute",
              inset: 0,
              border: "none",
              background: "transparent",
              padding: 0,
              margin: 0,
              cursor: "default",
            }}
          />
          <div
            style={{
              background: C.surface,
              borderRadius: 14,
              width: 380,
              maxWidth: "90vw",
              border: `1.5px solid ${C.border}`,
              boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
              overflow: "hidden",
              position: "relative",
              zIndex: 1,
            }}
          >
            <div
              style={{
                padding: "16px 20px 12px",
                borderBottom: `1px solid ${C.border}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    ...{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    },
                    background: `${currentLevelMeta.color}18`,
                  }}
                >
                  <span
                    style={{
                      ...{
                        display: "flex",
                      },
                      color: currentLevelMeta.color,
                    }}
                  >
                    {Ic.lock(16)}
                  </span>
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      fontFamily: F.sans,
                      color: C.text,
                    }}
                  >
                    Seal this REE?
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      fontFamily: F.sans,
                      color: C.textMuted,
                      marginTop: 1,
                    }}
                  >
                    This action cannot be undone.
                  </div>
                </div>
              </div>
            </div>

            {!allLive && (
              <div
                style={{
                  margin: "12px 20px 0",
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "#fffbeb",
                  border: "1.5px solid #fde68a",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 15,
                      flexShrink: 0,
                      lineHeight: 1.2,
                    }}
                  >
                    ⚠️
                  </span>
                  <div>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        fontFamily: F.sans,
                        color: "#92400e",
                        marginBottom: 5,
                      }}
                    >
                      {missing.length} panel{missing.length !== 1 ? "s" : ""} not connected
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 3,
                      }}
                    >
                      {missing.map((item) => (
                        <div
                          key={item.key}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <div
                            style={{
                              width: 5,
                              height: 5,
                              borderRadius: "50%",
                              background: "#f59e0b",
                              flexShrink: 0,
                            }}
                          />
                          <span
                            style={{
                              fontSize: 10,
                              fontFamily: F.sans,
                              color: "#92400e",
                            }}
                          >
                            {item.label} — not completed
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div
              style={{
                padding: "12px 20px",
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontFamily: F.sans,
                  color: C.textMid,
                  lineHeight: 1.6,
                }}
              >
                {allLive ? (
                  <>
                    All <strong>{totalCables}</strong> panels are connected. The REE will be frozen
                    at{" "}
                    <strong>
                      L{level} · {currentLevelMeta.label}
                    </strong>{" "}
                    and become read-only.
                  </>
                ) : (
                  <>
                    Sealing now will freeze the REE at{" "}
                    <strong>
                      L{level} · {currentLevelMeta.label}
                    </strong>{" "}
                    with incomplete data. You can still seal, but the missing panels will not be
                    part of the record.
                  </>
                )}
              </div>
            </div>

            <div
              style={{
                padding: "0 20px 16px",
                display: "flex",
                gap: 8,
                justifyContent: "flex-end",
              }}
            >
              <button
                type="button"
                onClick={() => setShowSealConfirm(false)}
                style={{
                  ...S_ACTION_BUTTON_BASE,
                  padding: "8px 16px",
                  borderRadius: 7,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  background: C.surfaceAlt,
                  color: C.textMid,
                  border: `1.5px solid ${C.border}`,
                }}
                {...hoverBg(C.border, C.surfaceAlt)}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowSealConfirm(false);
                  onSeal?.();
                }}
                style={{
                  ...{
                    ...S_ACTION_BUTTON_BASE,
                    display: "flex",
                    alignItems: "center",
                    gap: 7,
                    padding: "8px 18px",
                    borderRadius: 7,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    color: "#fff",
                  },
                  background: currentLevelMeta.color,
                  border: `1.5px solid ${currentLevelMeta.color}`,
                  boxShadow: `0 2px 8px ${currentLevelMeta.color}50`,
                }}
                {...hoverBrightness(90)}
              >
                <span style={{ display: "flex" }}>{Ic.lock(12)}</span>
                {allLive ? "Seal REE" : "Seal anyway"}
              </button>
            </div>
          </div>
        </div>
      )}

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
              fontFamily: F.sans,
              color: C.textMuted,
              flexShrink: 0,
            }}
          >
            {liveCount}/{totalCables} connected
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
                fontFamily: F.sans,
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
                  fontFamily: F.sans,
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
            onClick={() => setShowSealConfirm(true)}
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
    </>
  );
}

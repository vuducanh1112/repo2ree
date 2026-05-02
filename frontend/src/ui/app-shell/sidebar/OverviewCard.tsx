import type { AppShellPage } from "../../../application/app-shell/AppShellPages";
import { PAGE } from "../../../application/app-shell/AppShellPages";
import { C, F, hoverBg } from "../../theme/theme";
import { PodWidget } from "../pages/overview/PodWidget";
import type { getPodCableStates } from "../pages/overview/podCableState";

type PodCableState = ReturnType<typeof getPodCableStates>[number];

interface OverviewCardProps {
  navCollapsed: boolean;
  page: AppShellPage;
  level: number;
  levelMeta: {
    bg: string;
    color: string;
    ink: string;
  };
  cableStates: PodCableState[];
  leftCables: PodCableState[];
  rightCables: PodCableState[];
  topCable: PodCableState | null;
  setPage: (page: AppShellPage) => void;
}

function CableIndicator({
  connected,
  color,
  reverse = false,
}: {
  connected: boolean;
  color: string;
  reverse?: boolean;
}) {
  const dot = (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: connected ? color : C.borderMid,
        boxShadow: connected ? `0 0 8px ${color}88` : "none",
      }}
    />
  );
  const line = (
    <span
      style={{
        width: 28,
        height: 2,
        borderRadius: 99,
        background: connected ? color : C.border,
        opacity: connected ? 0.9 : 0.55,
        boxShadow: connected ? `0 0 7px ${color}55` : "none",
      }}
    />
  );

  return (
    <div
      style={{
        display: "flex",
        justifyContent: reverse ? "flex-end" : "flex-start",
        alignItems: "center",
        gap: 4,
      }}
    >
      {reverse ? line : dot}
      {reverse ? dot : line}
    </div>
  );
}

export function OverviewCard({
  navCollapsed,
  page,
  level,
  levelMeta,
  cableStates,
  leftCables,
  rightCables,
  topCable,
  setPage,
}: OverviewCardProps) {
  const isOverviewActive = page === PAGE.OVERVIEW;

  return (
    <div
      style={{
        padding: navCollapsed ? "8px 4px 8px" : "8px 8px 10px",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <button
        type="button"
        title={navCollapsed ? "Overview" : undefined}
        onClick={() => setPage(PAGE.OVERVIEW)}
        style={{
          width: "100%",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          padding: navCollapsed ? "6px 0" : "4px 2px 2px",
          borderRadius: 10,
        }}
        {...hoverBg(C.surfaceAlt, "transparent")}
      >
        {navCollapsed ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              minHeight: 40,
            }}
          >
            <PodWidget level={level} size={40} compact />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontFamily: F.sans,
                  fontWeight: 700,
                  color: isOverviewActive ? C.accent : C.text,
                  letterSpacing: 0.2,
                }}
              >
                REE
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.mono,
                  color: levelMeta.ink,
                  background: levelMeta.bg,
                  border: `1px solid ${levelMeta.color}44`,
                  borderRadius: 99,
                  padding: "1px 6px",
                }}
              >
                L{level}
              </span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto 1fr",
                alignItems: "center",
                gap: 6,
                borderRadius: 10,
                padding: "6px 6px",
                background: isOverviewActive ? `${levelMeta.color}08` : "transparent",
                outline: isOverviewActive
                  ? `1px solid ${levelMeta.color}44`
                  : "1px solid transparent",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {leftCables.map((cable) => (
                  <CableIndicator
                    key={cable.id}
                    connected={cable.connected}
                    color={cable.color}
                    reverse
                  />
                ))}
              </div>

              <PodWidget level={level} size={66} compact />

              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {rightCables.map((cable) => (
                  <CableIndicator key={cable.id} connected={cable.connected} color={cable.color} />
                ))}
              </div>
            </div>

            {topCable && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  marginTop: -2,
                  marginBottom: 2,
                }}
              >
                <span
                  style={{
                    width: 2,
                    height: 10,
                    borderRadius: 99,
                    background: topCable.connected ? topCable.color : C.border,
                    opacity: topCable.connected ? 0.95 : 0.55,
                    boxShadow: topCable.connected ? `0 0 7px ${topCable.color}55` : "none",
                  }}
                />
              </div>
            )}

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gap: 6,
              }}
            >
              {cableStates.map((cable) => (
                <div
                  key={cable.id}
                  style={{
                    fontSize: 9,
                    color: cable.connected ? C.textMid : C.textMuted,
                    fontFamily: F.mono,
                    textAlign: "center",
                    opacity: cable.connected ? 0.95 : 0.75,
                  }}
                >
                  {cable.connected ? "✓" : "·"} {cable.label}
                </div>
              ))}
            </div>
          </div>
        )}
      </button>
    </div>
  );
}

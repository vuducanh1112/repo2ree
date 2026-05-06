import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBg, hoverColor, hoverIf } from "../../../theme/theme";
import { CodeLineList, getFileTypeStyle, ScriptViewMessage } from "./shared";

export type ScriptPanelMode = "view" | "write";

function tabIcon(isActive: boolean, accent: string, icon: JSX.Element) {
  return <span style={{ display: "flex", color: isActive ? accent : C.textMuted }}>{icon}</span>;
}

export function ScriptPanelTabs(props: {
  tabs: Array<{ key: ScriptPanelMode; label: string; icon: () => JSX.Element }>;
  mode: ScriptPanelMode;
  collapsed: boolean;
  scriptPath: string;
  onModeChange: (mode: ScriptPanelMode) => void;
  onToggleCollapsed: () => void;
}) {
  const tabBg: Record<ScriptPanelMode, string> = { view: "#f0fdf4", write: "#f5f3ff" };
  const tabAccent: Record<ScriptPanelMode, string> = { view: "#16a34a", write: "#7c3aed" };
  const typeStyle = getFileTypeStyle(props.scriptPath);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        background: C.surfaceAlt,
        borderBottom: props.collapsed && props.mode === "view" ? "none" : `1px solid ${C.border}`,
      }}
    >
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {props.tabs.map((tab) => {
          const isActive = props.mode === tab.key;
          const accent = tabAccent[tab.key];
          return (
            <button
              type="button"
              key={tab.key}
              onClick={() => props.onModeChange(tab.key)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                border: "none",
                cursor: "pointer",
                transition: "background 0.13s",
                flexShrink: 0,
                background: isActive ? tabBg[tab.key] : "transparent",
                borderRight: `1px solid ${C.border}`,
                borderBottom: isActive ? `2px solid ${accent}` : "2px solid transparent",
              }}
              {...hoverIf(!isActive, hoverBg(`${C.border}40`, "transparent"))}
            >
              {tabIcon(isActive, accent, tab.icon())}
              <span
                style={{
                  fontSize: 12,
                  whiteSpace: "nowrap",
                  fontFamily: tab.key === "view" ? F.mono : F.sans,
                  color: isActive ? accent : C.textMid,
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {tab.label}
              </span>
              {tab.key === "view" && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.6,
                    textTransform: "uppercase",
                    padding: "1px 4px",
                    borderRadius: 3,
                    marginLeft: 2,
                    background: typeStyle.bg,
                    color: typeStyle.color,
                    border: `1px solid ${typeStyle.border}`,
                  }}
                >
                  {typeStyle.label}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {props.mode === "view" && (
        <button
          type="button"
          onClick={props.onToggleCollapsed}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "8px 12px",
            color: C.textMuted,
            display: "flex",
            alignItems: "center",
          }}
          {...hoverColor(C.textMid, C.textMuted)}
        >
          {props.collapsed ? Ic.chevD(13) : Ic.chevR(13)}
        </button>
      )}
    </div>
  );
}

export function ScriptPanelView({ viewLines }: { viewLines: string[] | null }) {
  return (
    <div style={{ background: C.surfaceAlt }}>
      {viewLines === null ? (
        <ScriptViewMessage color="#f97316">
          File not found in repository tree — check the path in metadata fields.
        </ScriptViewMessage>
      ) : viewLines.length === 0 ? (
        <ScriptViewMessage color={C.textMuted} fontStyle="italic">
          (empty file)
        </ScriptViewMessage>
      ) : (
        <div style={{ padding: "8px 0 10px" }}>
          <CodeLineList lines={viewLines} />
        </div>
      )}
    </div>
  );
}

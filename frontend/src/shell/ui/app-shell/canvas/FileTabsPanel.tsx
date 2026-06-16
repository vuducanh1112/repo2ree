import { useRef } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { FileViewer } from "../pages/files/FileViewer";
import type { FlatTreeEntry } from "../pages/files/filesPageHelpers";

const FILE_TABS_PANEL_WIDTH = 560;
const FILE_TABS_PANEL_HEIGHT = 620;

interface FileTabsPanelProps {
  openEntries: FlatTreeEntry[];
  activeEntry: FlatTreeEntry;
  left: number;
  top: number;
  onActivate: (id: string) => void;
  onClose: (id: string) => void;
}

export function FileTabsPanel({
  openEntries,
  activeEntry,
  left,
  top,
  onActivate,
  onClose,
}: FileTabsPanelProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleTabKeyDown = (e: React.KeyboardEvent, idx: number) => {
    let next = idx;
    if (e.key === "ArrowRight") next = (idx + 1) % openEntries.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + openEntries.length) % openEntries.length;
    if (next !== idx) {
      onActivate(openEntries[next].node.id);
      tabRefs.current[next]?.focus();
    }
  };

  return (
    <div
      data-canvas-hud
      style={{
        position: "absolute",
        left,
        top,
        width: FILE_TABS_PANEL_WIDTH,
        height: FILE_TABS_PANEL_HEIGHT,
        display: "flex",
        flexDirection: "column",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 24px 60px rgba(13,17,23,0.2)",
        animation: "dockIn 0.3s cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <div
        role="tablist"
        aria-label="Open files"
        style={{
          display: "flex",
          flexShrink: 0,
          borderBottom: `1px solid ${C.border}`,
          background: C.surfaceAlt,
        }}
      >
        <div style={{ display: "flex", flex: 1, minWidth: 0, overflowX: "auto" }}>
          {openEntries.map((entry, idx) => {
            const isActive = entry.node.id === activeEntry.node.id;
            return (
              <div
                key={entry.node.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "7px 8px 7px 12px",
                  maxWidth: 180,
                  flexShrink: 0,
                  background: isActive ? C.surface : "transparent",
                  borderRight: `1px solid ${C.border}`,
                  borderBottom: isActive ? `2px solid ${C.accent}` : "2px solid transparent",
                }}
              >
                <button
                  ref={(el) => {
                    tabRefs.current[idx] = el;
                  }}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => onActivate(entry.node.id)}
                  onKeyDown={(e) => handleTabKeyDown(e, idx)}
                  title={entry.path}
                  style={{
                    flex: 1,
                    minWidth: 0,
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    textAlign: "left",
                    padding: 0,
                    fontFamily: F.mono,
                    fontSize: 11.5,
                    color: isActive ? C.text : C.textMuted,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {entry.node.name}
                </button>
                <button
                  type="button"
                  aria-label={`Close ${entry.node.name}`}
                  onClick={() => onClose(entry.node.id)}
                  style={{
                    display: "flex",
                    flexShrink: 0,
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: C.textMuted,
                    padding: 2,
                    borderRadius: 4,
                  }}
                >
                  {Ic.x(11)}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <FileViewer key={activeEntry.node.id} file={activeEntry.node} />
      </div>
    </div>
  );
}

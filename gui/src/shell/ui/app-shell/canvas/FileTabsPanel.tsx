import { useRef } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { FileViewer } from "../pages/files/FileViewer";
import type { FlatTreeEntry } from "../pages/files/filesPageHelpers";
import { CanvasWindow, CanvasWindowTitle } from "./CanvasWindow";

// Grow with the canvas instead of a fixed 560×620: small viewports get a
// panel that still fits beside the tree, large ones get a real editor-sized
// window. The caps keep it from sprawling under the top-right REE console.
const PANEL_MARGIN = 16;
const FILE_TABS_PANEL_MIN_WIDTH = 420;
const FILE_TABS_PANEL_MAX_WIDTH = 920;
const FILE_TABS_PANEL_MIN_HEIGHT = 320;
const FILE_TABS_PANEL_MAX_HEIGHT = 820;

interface FileTabsPanelProps {
  openEntries: FlatTreeEntry[];
  activeEntry: FlatTreeEntry;
  left: number;
  top: number;
  onActivate: (id: string) => void;
  onClose: (id: string) => void;
  onDismiss: () => void;
}

export function FileTabsPanel({
  openEntries,
  activeEntry,
  left,
  top,
  onActivate,
  onClose,
  onDismiss,
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
    <CanvasWindow
      ariaLabel="Open files"
      onClose={onDismiss}
      header={
        <CanvasWindowTitle
          icon={Ic.files(15)}
          iconColor={C.textMuted}
          title="Files"
          subtitle={`${openEntries.length} open`}
        />
      }
      outerStyle={{
        position: "absolute",
        left,
        top,
        width: `clamp(${FILE_TABS_PANEL_MIN_WIDTH}px, calc(100% - ${left + PANEL_MARGIN}px), ${FILE_TABS_PANEL_MAX_WIDTH}px)`,
        height: `clamp(${FILE_TABS_PANEL_MIN_HEIGHT}px, calc(100% - ${top + PANEL_MARGIN}px), ${FILE_TABS_PANEL_MAX_HEIGHT}px)`,
        animation: "dockIn 0.3s cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <div
        role="tablist"
        aria-label="Open file tabs"
        style={{
          display: "flex",
          flexShrink: 0,
          borderBottom: `1px solid ${C.border}`,
          background: C.surfaceAlt,
          overflowX: "auto",
        }}
      >
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

      <div
        title={activeEntry.path}
        style={{
          flexShrink: 0,
          padding: "4px 12px",
          borderBottom: `1px solid ${C.border}`,
          fontFamily: F.mono,
          fontSize: 10.5,
          color: C.textMuted,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          direction: "rtl",
          textAlign: "left",
        }}
      >
        {activeEntry.path}
      </div>

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <FileViewer key={activeEntry.node.id} file={activeEntry.node} />
      </div>
    </CanvasWindow>
  );
}

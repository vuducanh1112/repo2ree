import type { FlatTreeEntry } from "@core/workspace/reeFileTree";
import { useRef } from "react";
import { Ic } from "../../shared/components/Icon";
import { FileViewer } from "../pages/files/FileViewer";
import { CanvasWindow, CanvasWindowTitle } from "./CanvasWindow";
import styles from "./FileTabsPanel.module.css";

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
          title="Files"
          subtitle={`${openEntries.length} open`}
        />
      }
      className={styles.panel}
      vars={{ "--tabs-left": `${left}px`, "--tabs-top": `${top}px` }}
    >
      <div role="tablist" aria-label="Open file tabs" className={styles.tabs}>
        {openEntries.map((entry, idx) => {
          const isActive = entry.node.id === activeEntry.node.id;
          return (
            <div key={entry.node.id} className={styles.tab} data-active={isActive || undefined}>
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
                className={styles.tabName}
              >
                {entry.node.name}
              </button>
              <button
                type="button"
                aria-label={`Close ${entry.node.name}`}
                onClick={() => onClose(entry.node.id)}
                className={styles.tabClose}
              >
                {Ic.x(11)}
              </button>
            </div>
          );
        })}
      </div>

      <div title={activeEntry.path} className={styles.path}>
        {activeEntry.path}
      </div>

      <div className={styles.viewerSlot}>
        <FileViewer key={activeEntry.node.id} file={activeEntry.node} />
      </div>
    </CanvasWindow>
  );
}

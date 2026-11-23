import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { filterFileTree } from "@core/workspace/fileTreeFilter";
import { useEffect, useMemo, useRef, useState } from "react";
import { FileNode } from "../../shared/components/FileTree";
import { Ic } from "../../shared/components/Icon";
import { FileFilterInput } from "../pages/files/FileFilterInput";
import { useFileConsoleTrees } from "../pages/files/useFileConsoleTrees";
import { FileTabsPanel } from "./FileTabsPanel";
import styles from "./FileTreeConsole.module.css";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";

const HUD_LEFT = 16;
const HUD_TOP = 16;
const HUD_WIDTH_OPEN = 286;
const HUD_WIDTH_COLLAPSED = 238;
const VIEWER_GAP = 12;

interface FileTreeConsoleProps {
  workspaceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  externallyTriggered?: boolean;
}

export function FileTreeConsole({
  workspaceFiles,
  reeFiles,
  open,
  onOpenChange,
  externallyTriggered = false,
}: FileTreeConsoleProps) {
  const [query, setQuery] = useState("");
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [viewerDismissed, setViewerDismissed] = useState(false);

  const { reeTree, entryById, workspaceFileCount, reeFileCount } = useFileConsoleTrees(
    workspaceFiles,
    reeFiles,
  );
  const filtering = query.trim().length > 0;
  const filteredWorkspace = useMemo(
    () => (filtering ? filterFileTree(workspaceFiles, query) : workspaceFiles),
    [workspaceFiles, query, filtering],
  );
  const filteredRee = useMemo(
    () => (filtering ? filterFileTree(reeTree, query) : reeTree),
    [reeTree, query, filtering],
  );

  useEffect(() => {
    setOpenTabs((tabs) => {
      const pruned = tabs.filter((id) => entryById.has(id));
      return pruned.length === tabs.length ? tabs : pruned;
    });
  }, [entryById]);

  const openEntries = openTabs
    .map((id) => entryById.get(id))
    .filter((entry): entry is NonNullable<typeof entry> => !!entry);
  const activeEntry =
    (activeId ? entryById.get(activeId) : undefined) ?? openEntries[openEntries.length - 1] ?? null;

  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const openRef = useRef(open);
  openRef.current = open;
  const onOpenChangeRef = useRef(onOpenChange);
  onOpenChangeRef.current = onOpenChange;
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (activeIdRef.current) setActiveId(null);
      if (openRef.current) onOpenChangeRef.current(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  const openFile = (id: string) => {
    setOpenTabs((tabs) => (tabs.includes(id) ? tabs : [...tabs, id]));
    setActiveId(id);
    setViewerDismissed(false);
  };
  const closeTab = (id: string) => {
    const idx = openTabs.indexOf(id);
    const next = openTabs.filter((tab) => tab !== id);
    setOpenTabs(next);
    if (activeId === id) {
      setActiveId(next.length ? next[Math.min(idx, next.length - 1)] : null);
    }
  };

  const hudWidth = open ? HUD_WIDTH_OPEN : HUD_WIDTH_COLLAPSED;
  const fileCount = workspaceFileCount + reeFileCount;
  const sharing = filteredWorkspace.length > 0 && filteredRee.length > 0;

  return (
    <>
      {(!externallyTriggered || open) && (
        <HudConsole
          open={open}
          onToggle={() => {
            if (open) setActiveId(null);
            onOpenChange(!open);
          }}
          widthOpen={HUD_WIDTH_OPEN}
          widthCollapsed={HUD_WIDTH_COLLAPSED}
          className={hud.filesPlacement}
          icon={Ic.files(16)}
          title="Files"
          subtitle={
            fileCount > 0
              ? `${workspaceFileCount} workspace · ${reeFileCount} REE`
              : "REE filesystem"
          }
          on={fileCount > 0}
          expandLabel="Expand files"
          collapseLabel="Collapse files"
        >
          <FileFilterInput query={query} onChange={setQuery} />
          <div className={styles.tree}>
            <TreeSection
              inventory="workspace"
              title="Workspace"
              nodes={filteredWorkspace}
              empty={
                filtering
                  ? "No matching workspace files"
                  : "Acquire source to materialize the workspace."
              }
              defaultOpenDepth={0}
              share={sharing}
              selectedId={activeEntry?.node.id ?? null}
              filtering={filtering}
              onSelect={openFile}
            />
            <TreeSection
              inventory="ree"
              title="REE"
              nodes={filteredRee}
              empty={
                filtering ? "No matching REE files" : "Run lifecycle steps to populate the REE."
              }
              share={sharing}
              selectedId={activeEntry?.node.id ?? null}
              filtering={filtering}
              onSelect={openFile}
            />
          </div>
        </HudConsole>
      )}

      {open && !viewerDismissed && activeEntry && (
        <FileTabsPanel
          openEntries={openEntries}
          activeEntry={activeEntry}
          left={HUD_LEFT + hudWidth + VIEWER_GAP}
          top={HUD_TOP}
          onActivate={setActiveId}
          onClose={closeTab}
          onDismiss={() => setViewerDismissed(true)}
        />
      )}
    </>
  );
}

interface TreeSectionProps {
  inventory: "workspace" | "ree";
  title: string;
  nodes: FileTreeNode[];
  empty: string;
  defaultOpenDepth?: number;
  share?: boolean;
  selectedId: string | null;
  filtering: boolean;
  onSelect: (id: string) => void;
}

function TreeSection({
  inventory,
  title,
  nodes,
  empty,
  defaultOpenDepth,
  share,
  selectedId,
  filtering,
  onSelect,
}: TreeSectionProps) {
  return (
    <div className={styles.section} data-inventory={inventory} data-share={share || undefined}>
      <div className={styles.sectionTitle}>{title}</div>
      <div className={styles.sectionScroll}>
        {nodes.length === 0 ? (
          <div className={styles.empty}>{empty}</div>
        ) : (
          nodes.map((node) => (
            <FileNode
              key={node.id}
              node={node}
              onSelect={(picked) => onSelect(picked.id)}
              selectedId={selectedId}
              forceOpen={filtering}
              defaultOpenDepth={defaultOpenDepth}
            />
          ))
        )}
      </div>
    </div>
  );
}

import type { ReeFile } from "@core/ree/ReeTypes";
import { filterFileTree } from "@core/workspace/fileTreeFilter";
import { useEffect, useMemo, useRef, useState } from "react";
import { FileNode } from "../../shared/components/FileTree";
import { Ic } from "../../shared/components/Icon";
import { FileFilterInput } from "../pages/files/FileFilterInput";
import { useReeFileTree } from "../pages/files/useReeFileTree";
import { FileTabsPanel } from "./FileTabsPanel";
import styles from "./FileTreeConsole.module.css";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";

const HUD_LEFT = 16;
const HUD_TOP = 16;
const HUD_WIDTH_OPEN = 286;
const HUD_WIDTH_COLLAPSED = 222;
const VIEWER_GAP = 12;

interface FileTreeConsoleProps {
  reeFiles: ReeFile[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// The file tree is the workbench's filesystem — ambient lab context, not a
// lifecycle stage — so it docks as a HUD console pinned to the upper-left
// corner, mirroring the BenchConsole in the lower-left. Selecting a file pops
// the viewer beside it so the tree stays live for browsing.
export function FileTreeConsole({ reeFiles, open, onOpenChange }: FileTreeConsoleProps) {
  const [query, setQuery] = useState("");
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  // Header X hides the viewer window without forgetting the open tabs;
  // picking any file in the tree brings it back.
  const [viewerDismissed, setViewerDismissed] = useState(false);

  const { tree, entryById } = useReeFileTree(reeFiles);
  const filtering = query.trim().length > 0;
  const filtered = useMemo(
    () => (filtering ? filterFileTree(tree, query) : tree),
    [tree, query, filtering],
  );

  // Drop tabs whose files no longer exist (e.g. after re-acquiring source).
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

  // Escape collapses the whole console (viewer + tree) so it stops blocking
  // canvas nodes — the open tree covers left-side nodes even without the viewer.
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
  const fileCount = reeFiles.length;

  return (
    <>
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
            ? `${fileCount} file${fileCount !== 1 ? "s" : ""} on disk`
            : "REE filesystem"
        }
        on={fileCount > 0}
        expandLabel="Expand files"
        collapseLabel="Collapse files"
      >
        <FileFilterInput query={query} onChange={setQuery} />
        <div className={styles.tree}>
          {filtered.length === 0 ? (
            <div className={styles.empty}>
              {filtering
                ? "No matching REE files"
                : fileCount === 0
                  ? "Acquire source and run lifecycle steps to populate the REE."
                  : "No REE files"}
            </div>
          ) : (
            filtered.map((node) => (
              <FileNode
                key={node.id}
                node={node}
                onSelect={(picked) => openFile(picked.id)}
                selectedId={activeEntry?.node.id ?? null}
                forceOpen={filtering}
              />
            ))
          )}
        </div>
      </HudConsole>

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

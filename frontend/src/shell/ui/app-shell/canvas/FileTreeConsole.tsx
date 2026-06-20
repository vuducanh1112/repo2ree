import type { ReeFile } from "@core/ree/ReeTypes";
import { filterFileTree } from "@core/workspace/fileTreeFilter";
import { useEffect, useMemo, useRef, useState } from "react";
import { FileNode } from "../../shared/components/FileTree";
import { Ic } from "../../shared/components/Icon";
import { lgColors } from "../../theme/lightGlassTheme";
import { F } from "../../theme/theme";
import { FileFilterInput } from "../pages/files/FileFilterInput";
import { useReeFileTree } from "../pages/files/useReeFileTree";
import { FileTabsPanel } from "./FileTabsPanel";
import { HudConsole } from "./HudConsole";

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
        outerStyle={{
          left: HUD_LEFT,
          top: HUD_TOP,
          maxHeight: "calc(100% - 32px)",
          display: "flex",
          flexDirection: "column",
        }}
        icon={Ic.files(16)}
        iconColor={lgColors.textMuted}
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
        <div style={{ overflowY: "auto", padding: "0 4px 8px", maxHeight: "min(52vh, 460px)" }}>
          {filtered.length === 0 ? (
            <div
              style={{
                padding: "10px 12px",
                fontSize: 11,
                color: lgColors.textMuted,
                fontFamily: F.sans,
                fontStyle: "italic",
              }}
            >
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

      {open && activeEntry && (
        <FileTabsPanel
          openEntries={openEntries}
          activeEntry={activeEntry}
          left={HUD_LEFT + hudWidth + VIEWER_GAP}
          top={HUD_TOP}
          onActivate={setActiveId}
          onClose={closeTab}
        />
      )}
    </>
  );
}

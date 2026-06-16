import { useEffect, useMemo, useRef, useState } from "react";
import type { ReeFile } from "../../../../core/ree/ReeTypes";
import { filterFileTree } from "../../../../core/workspace/fileTreeFilter";
import { FileNode } from "../../shared/components/FileTree";
import { Ic } from "../../shared/components/Icon";
import { lgColors } from "../../theme/lightGlassTheme";
import { C, F } from "../../theme/theme";
import { FileFilterInput } from "../pages/files/FileFilterInput";
import { useReeFileTree } from "../pages/files/useReeFileTree";
import { FileTabsPanel } from "./FileTabsPanel";

const DONE = "#10b981";

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

  return (
    <>
      <div
        data-canvas-hud
        style={{
          position: "absolute",
          left: HUD_LEFT,
          top: HUD_TOP,
          width: hudWidth,
          maxHeight: "calc(100% - 32px)",
          display: "flex",
          flexDirection: "column",
          background: "rgba(255,255,255,0.92)",
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          boxShadow: open ? "0 18px 48px rgba(13,17,23,0.16)" : "0 4px 14px rgba(13,17,23,0.08)",
          backdropFilter: "blur(4px)",
          overflow: "hidden",
          transition: "width 0.26s cubic-bezier(0.4,0,0.2,1), box-shadow 0.26s",
        }}
      >
        <button
          type="button"
          aria-expanded={open}
          aria-label={open ? "Collapse files" : "Expand files"}
          onClick={() => {
            if (open) setActiveId(null);
            onOpenChange(!open);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            width: "100%",
            padding: "9px 12px",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            textAlign: "left",
            flexShrink: 0,
          }}
        >
          <span style={{ color: lgColors.textMuted, display: "flex" }}>{Ic.files(16)}</span>
          <div
            style={{
              flex: 1,
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              lineHeight: 1.3,
            }}
          >
            <span style={{ fontSize: 12, fontWeight: 650, color: C.text }}>Files</span>
            <span
              style={{
                fontFamily: F.mono,
                fontSize: 9.5,
                color: C.textMuted,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {reeFiles.length > 0
                ? `${reeFiles.length} file${reeFiles.length !== 1 ? "s" : ""} on disk`
                : "REE filesystem"}
            </span>
          </div>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              flexShrink: 0,
              background: reeFiles.length > 0 ? DONE : C.borderMid,
              boxShadow: reeFiles.length > 0 ? `0 0 7px ${DONE}88` : "none",
            }}
          />
          <span
            style={{
              display: "flex",
              color: C.textMuted,
              flexShrink: 0,
              transform: open ? "rotate(180deg)" : "none",
              transition: "transform 0.26s",
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <title>toggle</title>
              <path
                d="M6 15l6-6 6 6"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </button>

        {open && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              borderTop: `1px solid ${C.border}`,
            }}
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
                    : reeFiles.length === 0
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
          </div>
        )}
      </div>

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

import { useMemo, useState } from "react";
import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { filterFileTree } from "../../../../../core/workspace/fileTreeFilter";
import { FileNode } from "../../../shared/components/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgTree } from "../../../theme/lightGlassTheme";
import { F, S_SECTION_LABEL } from "../../../theme/theme";

interface SectionHeaderProps {
  label: string;
  badge?: string;
  color: string;
}

function SectionHeader({ label, badge, color }: SectionHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "7px 10px 5px",
        position: "sticky",
        top: 0,
        background: lgTree.sectionBg,
        backdropFilter: "blur(6px)",
        zIndex: 1,
        borderBottom: `1px solid ${lgTree.pane.borderColor}`,
      }}
    >
      <div style={{ width: 3, height: 12, borderRadius: 99, background: color, flexShrink: 0 }} />
      <span
        style={{
          ...S_SECTION_LABEL,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 1.3,
          color: lgColors.textMid,
          flex: 1,
        }}
      >
        {label}
      </span>
      {badge && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: lgColors.textMuted,
            background: lgTree.chipBg,
            border: `1px solid ${lgTree.pane.borderColor}`,
            borderRadius: 3,
            padding: "1px 5px",
            fontFamily: F.sans,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        fontSize: 11,
        color: lgColors.textMuted,
        fontFamily: F.sans,
        fontStyle: "italic",
      }}
    >
      {text}
    </div>
  );
}

interface FilesTreePaneProps {
  sourceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  reeFileTree: FileTreeNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  hasSelection: boolean;
}

export function FilesTreePane({
  sourceFiles,
  reeFiles,
  reeFileTree,
  selectedId,
  onSelect,
  hasSelection,
}: FilesTreePaneProps) {
  const [query, setQuery] = useState("");
  const filtering = query.trim().length > 0;
  const filteredSource = useMemo(() => filterFileTree(sourceFiles, query), [sourceFiles, query]);
  const filteredRee = useMemo(() => filterFileTree(reeFileTree, query), [reeFileTree, query]);

  return (
    <div
      style={{
        width: hasSelection ? 220 : 300,
        borderRight: `1px solid ${lgTree.pane.borderColor}`,
        background: lgTree.pane.background,
        backdropFilter: "blur(12px)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
        transition: "width 0.18s",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          margin: "8px 8px 6px",
          padding: "0 8px",
          borderRadius: 7,
          border: `1px solid ${lgTree.pane.borderColor}`,
          background: lgTree.inputBg,
        }}
      >
        <span style={{ display: "flex", color: lgColors.textMuted, flexShrink: 0 }}>
          {Ic.search(13)}
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter files…"
          aria-label="Filter files"
          style={{
            flex: 1,
            minWidth: 0,
            border: "none",
            outline: "none",
            background: "transparent",
            padding: "7px 0",
            fontSize: 12,
            fontFamily: F.sans,
            color: lgColors.text,
          }}
        />
        {filtering && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear filter"
            style={{
              display: "flex",
              alignItems: "center",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: lgColors.textMuted,
              padding: 2,
              flexShrink: 0,
            }}
          >
            {Ic.x(12)}
          </button>
        )}
      </div>

      <div style={{ overflowY: "auto", flex: 1 }}>
        <SectionHeader label="Workspace" badge="read-only" color="#f59e0b" />
        <div style={{ padding: "4px 4px 8px" }}>
          {filteredSource.length === 0 ? (
            <EmptyHint text={filtering ? "No matching workspace files" : "No workspace files"} />
          ) : (
            filteredSource.map((sourceNode) => (
              <FileNode
                key={sourceNode.id}
                node={sourceNode}
                onSelect={(selectedNode) => onSelect(selectedNode.id)}
                selectedId={selectedId}
                forceOpen={filtering}
              />
            ))
          )}
        </div>

        <SectionHeader
          label="REE Files"
          badge={`${reeFiles.length} file${reeFiles.length !== 1 ? "s" : ""}`}
          color={lgColors.violet}
        />
        <div style={{ padding: "4px 4px 8px" }}>
          {filteredRee.length === 0 ? (
            <EmptyHint
              text={
                filtering
                  ? "No matching REE files"
                  : reeFiles.length === 0
                    ? "Run Create & Build to generate files"
                    : "No REE files"
              }
            />
          ) : (
            filteredRee.map((reeNode) => (
              <FileNode
                key={reeNode.id}
                node={reeNode}
                onSelect={(selectedNode) => onSelect(selectedNode.id)}
                selectedId={selectedId}
                forceOpen={filtering}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

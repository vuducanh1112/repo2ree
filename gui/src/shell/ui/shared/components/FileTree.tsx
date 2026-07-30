import type { FileTreeNode } from "@core/workspace/FileTree";
import { classifyFileType } from "@core/workspace/PathUtils";
import { useState } from "react";
import { lgColors, lgFileTypeColor, lgTree } from "../../theme/lightGlassTheme";
import { F, hoverBg, hoverIf } from "../../theme/theme";
import { Ic } from "./Icon";

interface FileNodeProps {
  node: FileTreeNode;
  depth?: number;
  onSelect: (node: FileTreeNode) => void;
  selectedId: string | null;
  highlightedPaths?: Set<string>;
  /** Force every folder open (used while a filter is active). */
  forceOpen?: boolean;
}

function fileTypeIcon(name: string, size: number) {
  const category = classifyFileType(name);
  const glyph =
    category === "code"
      ? Ic.fileCode(size)
      : category === "archive"
        ? Ic.fileArchive(size)
        : Ic.file(size);
  return { glyph, color: lgFileTypeColor(category) };
}

export function FileNode({
  node,
  depth = 0,
  onSelect,
  selectedId,
  highlightedPaths = new Set(),
  forceOpen = false,
}: FileNodeProps) {
  const [open, setOpen] = useState(depth < 1);
  const isFolder = node.type === "folder";
  const isSel = selectedId === node.id;
  const isHighlighted = !isFolder && highlightedPaths.has(node.name);
  const isOpen = forceOpen || open;
  const fileIcon = isFolder ? null : fileTypeIcon(node.name, 14);

  const handleNodeClick = () => {
    if (isFolder) {
      setOpen(!open);
    } else {
      onSelect(node);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={handleNodeClick}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          padding: "4px 8px",
          borderRadius: 5,
          cursor: "pointer",
          fontSize: 13,
          fontFamily: F.mono,
          transition: "background 0.1s",
          userSelect: "none",
          textAlign: "left",
          width: "100%",
          paddingLeft: 8 + depth * 14,
          background: isSel
            ? lgTree.selectedBg
            : isHighlighted
              ? lgTree.highlightBg
              : "transparent",
          border: `1px solid ${
            isSel ? lgTree.selectedBorder : isHighlighted ? lgTree.highlightBorder : "transparent"
          }`,
          color: isSel
            ? lgTree.selectedText
            : isHighlighted
              ? lgTree.highlightText
              : isFolder
                ? lgColors.text
                : lgColors.textMid,
        }}
        {...hoverIf(
          !isSel,
          hoverBg(
            isHighlighted ? lgTree.highlightBg : lgTree.hoverBg,
            isHighlighted ? lgTree.highlightBg : "transparent",
          ),
        )}
      >
        {isFolder ? (
          <>
            <span
              style={{
                color: lgColors.textMuted,
                display: "flex",
                width: 12,
              }}
            >
              {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
            {Ic.folder(14)}
          </>
        ) : (
          <span
            style={{
              marginLeft: 12,
              display: "flex",
              color: isSel ? lgTree.selectedText : fileIcon?.color,
            }}
          >
            {fileIcon?.glyph}
          </span>
        )}
        <span
          style={{
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {node.name}
        </span>
        {isHighlighted && !isSel && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              color: lgTree.highlightText,
              background: lgTree.highlightBg,
              border: `1px solid ${lgTree.highlightBorder}`,
              borderRadius: 3,
              padding: "0 3px",
              fontFamily: F.sans,
              flexShrink: 0,
            }}
          >
            REF
          </span>
        )}
      </button>
      {isFolder &&
        isOpen &&
        node.children?.map((c) => (
          <FileNode
            key={c.id}
            node={c}
            depth={depth + 1}
            onSelect={onSelect}
            selectedId={selectedId}
            highlightedPaths={highlightedPaths}
            forceOpen={forceOpen}
          />
        ))}
    </div>
  );
}

import type { FileTreeNode } from "@core/workspace/FileTree";
import { classifyFileType } from "@core/workspace/PathUtils";
import { useState } from "react";
import { cssVars } from "../../theme/styleVars";
import styles from "./FileTree.module.css";
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

// The glyph and the category it belongs to; how the category *reads* is in
// FileTree.module.css, keyed off the same value classifyFileType returns.
function fileTypeIcon(name: string, size: number) {
  const category = classifyFileType(name);
  const glyph =
    category === "code"
      ? Ic.fileCode(size)
      : category === "archive"
        ? Ic.fileArchive(size)
        : Ic.file(size);
  return { glyph, category };
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
        className={styles.row}
        data-kind={isFolder ? "folder" : "file"}
        data-selected={isSel || undefined}
        data-marked={isHighlighted && !isSel ? true : undefined}
        style={cssVars({ "--tree-depth": depth })}
      >
        {isFolder ? (
          <>
            <span aria-hidden className={styles.chevron}>
              {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
            {Ic.folder(14)}
          </>
        ) : (
          <span aria-hidden className={styles.fileIcon} data-category={fileIcon?.category}>
            {fileIcon?.glyph}
          </span>
        )}
        <span className={styles.name}>{node.name}</span>
        {isHighlighted && !isSel && <span className={styles.marker}>REF</span>}
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

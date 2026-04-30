import { useState } from "react";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { C, F, hoverBg, hoverIf } from "../../theme/theme";
import { Ic } from "./Icon";

interface FileNodeProps {
  node: FileTreeNode;
  depth?: number;
  onSelect: (node: FileTreeNode) => void;
  selectedId: string | null;
  highlightedPaths?: Set<string>;
}

export function FileNode({
  node,
  depth = 0,
  onSelect,
  selectedId,
  highlightedPaths = new Set(),
}: FileNodeProps) {
  const [open, setOpen] = useState(depth < 1);
  const isFolder = node.type === "folder";
  const isSel = selectedId === node.id;
  const isHighlighted = !isFolder && highlightedPaths.has(node.name);

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
          background: isSel ? C.accentBg : isHighlighted ? "#fef3c7" : "transparent",
          border: isHighlighted && !isSel ? "1px solid #fde68a" : "1px solid transparent",
          color: isSel ? C.accent : isHighlighted ? "#92400e" : isFolder ? C.text : C.textMid,
        }}
        {...hoverIf(
          !isSel,
          hoverBg(
            isHighlighted ? "#fef3c7" : C.surfaceAlt,
            isHighlighted ? "#fef3c7" : "transparent",
          ),
        )}
      >
        {isFolder ? (
          <>
            <span
              style={{
                color: C.textMuted,
                display: "flex",
                width: 12,
              }}
            >
              {open ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
            {Ic.folder(14)}
          </>
        ) : (
          <span
            style={{
              marginLeft: 12,
              display: "flex",
            }}
          >
            {Ic.file(14)}
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
              color: "#b45309",
              background: "#fef3c7",
              border: "1px solid #fde68a",
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
        open &&
        node.children?.map((c) => (
          <FileNode
            key={c.id}
            node={c}
            depth={depth + 1}
            onSelect={onSelect}
            selectedId={selectedId}
            highlightedPaths={highlightedPaths}
          />
        ))}
    </div>
  );
}

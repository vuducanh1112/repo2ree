import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { C, F, S_SECTION_LABEL_SMALL, S_STATUS_BADGE_SM_BASE } from "../../../theme/theme";

interface RuntimeOutputNodeProps {
  expectedOutput: string;
  buildDone: boolean;
  ree: ReeEditorViewModel;
  imageColor: string;
  files: FileTreeNode[];
}
export function RuntimeOutputNode({
  expectedOutput,
  buildDone,
  ree,
  imageColor,
  files,
}: RuntimeOutputNodeProps) {
  const isTarball = expectedOutput && /\.(tar|tar\.gz|tgz)$/i.test(expectedOutput);
  const alreadySet = expectedOutput && ree.runtime === expectedOutput;

  const fileExists = isTarball
    ? !!(function find(nodes: FileTreeNode[]): FileTreeNode | undefined {
        for (const node of nodes || []) {
          if (
            node.type === "file" &&
            (node.name === expectedOutput || expectedOutput.endsWith(`/${node.name}`))
          )
            return node;
          if (node.children) {
            const foundNode = find(node.children);
            if (foundNode) return foundNode;
          }
        }
      })(files || [])
    : false;

  const state = !expectedOutput
    ? "unset"
    : !buildDone
      ? "pending"
      : fileExists
        ? "found"
        : "missing";

  const colors = {
    unset: { border: C.border, bg: C.surfaceAlt, text: C.textMuted, icon: C.textMuted },
    pending: { border: C.accentBorder, bg: C.accentBg, text: C.accent, icon: C.accent },
    found: { border: `${imageColor}60`, bg: "#ecfeff", text: imageColor, icon: imageColor },
    missing: { border: "#fca5a5", bg: "#fef2f2", text: "#dc2626", icon: "#dc2626" },
  };
  const col = colors[state];
  const hasActionRow = state === "missing";

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: col.bg,
          border: `1.5px solid ${col.border}`,
          borderRadius: hasActionRow ? "8px 8px 0 0" : 8,
          transition: "all 0.3s",
          boxShadow: expectedOutput ? `0 0 0 3px ${col.border}30` : "none",
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: `${col.icon}18`,
          }}
        >
          <span style={{ color: col.icon, display: "flex" }}>{Ic.archive(14)}</span>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              ...S_SECTION_LABEL_SMALL,
              letterSpacing: 0.8,
              color: col.text,
              opacity: 0.7,
              marginBottom: 1,
            }}
          >
            {state === "unset" ? "Build output" : "Runtime file"}
          </div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              fontFamily: F.mono,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: col.text,
            }}
          >
            {expectedOutput || (
              <span
                style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11, color: C.textMuted }}
              >
                not specified
              </span>
            )}
          </div>
          {expectedOutput && (
            <div
              style={{
                fontSize: 10,
                color: col.text,
                opacity: 0.7,
                fontFamily: F.sans,
                marginTop: 1,
              }}
            >
              {state === "pending" && "will be checked after build runs"}
              {state === "found" && "✓ produced by build"}
              {state === "missing" && "✗ not found after build"}
            </div>
          )}
        </div>
        {state === "found" && (
          <span
            style={{
              ...S_STATUS_BADGE_SM_BASE,
              color: imageColor,
              background: `${imageColor}18`,
              border: `1px solid ${imageColor}40`,
            }}
          >
            FOUND
          </span>
        )}
        {state === "missing" && (
          <span
            style={{
              ...S_STATUS_BADGE_SM_BASE,
              color: "#dc2626",
              background: "#fef2f2",
              border: "1px solid #fecaca",
            }}
          >
            NOT FOUND
          </span>
        )}
        {alreadySet && (
          <span
            style={{
              ...S_STATUS_BADGE_SM_BASE,
              color: "#16a34a",
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
            }}
          >
            SET
          </span>
        )}
      </div>

      {state === "missing" && (
        <div
          style={{
            padding: "9px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderTop: "none",
            borderRadius: "0 0 8px 8px",
          }}
        >
          <span style={{ fontSize: 11, color: "#dc2626", fontFamily: F.sans, lineHeight: 1.4 }}>
            Expected <code style={{ fontFamily: F.mono, fontSize: 10.5 }}>{expectedOutput}</code>{" "}
            but it wasn't produced. Check your build script writes to this path.
          </span>
        </div>
      )}
    </div>
  );
}

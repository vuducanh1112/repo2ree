import type React from "react";
import { useState } from "react";
import {
  type DepGroup,
  ECO_META,
  PIN_META,
} from "../../../../application/workflow/workflowDependencyAnalysis";
import { Ic } from "../../../../components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
  S_SECTION_LABEL,
  S_SECTION_LABEL_SMALL,
  S_STATUS_BADGE_SM_BASE,
  S_TEXT_MUTED_11,
} from "../../../../constants/theme";
import type { FileTreeNode, LogEntry, Ree } from "../../../../types";
import { LogPanel } from "../inputs/logPanel";
import { workflowSectionCardStyle } from "./statusUiStyles";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

interface ServiceActionSectionProps {
  color: string;
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  idleLabel: string;
  runningLabel: string;
  doneLabel?: string;
  helperText: string;
  onRun: () => void;
  onCancel?: () => void;
}
export function WorkflowRunActionSection({
  color,
  running,
  runDone,
  disabled,
  idleLabel,
  runningLabel,
  doneLabel = "Re-run",
  helperText,
  onRun,
  onCancel,
}: ServiceActionSectionProps) {
  const buttonLabel = running ? runningLabel : runDone ? doneLabel : idleLabel;
  return (
    <div
      style={{ padding: "20px 24px 16px", flexShrink: 0, borderBottom: `1px solid ${C.border}` }}
    >
      <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Action</div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{
            ...actionBtn({
              border: "none",
              borderRadius: 8,
              padding: "8px 18px",
              fontWeight: 700,
            }),
            display: "flex",
            alignItems: "center",
            gap: 7,
            background: disabled ? `${color}22` : color,
            cursor: disabled ? "default" : "pointer",
            color: disabled ? color : "#fff",
          }}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : Ic.play(14)}
          </span>
          {buttonLabel}
        </button>
        {running && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            style={{
              ...actionBtn({
                borderRadius: 8,
                padding: "8px 14px",
                fontWeight: 700,
              }),
              display: "flex",
              alignItems: "center",
              gap: 7,
              background: "#fff1f2",
              border: "1.5px solid #fecdd3",
              color: "#be123c",
              cursor: "pointer",
            }}
          >
            {Ic.x(14)} Cancel
          </button>
        )}
        <div style={S_TEXT_MUTED_11}>{helperText}</div>
      </div>
    </div>
  );
}

interface WorkflowLogSectionProps {
  log: LogEntry | null;
  running: boolean;
  title?: string;
  titleStyle?: React.CSSProperties;
}
export function WorkflowLogSection({
  log,
  running,
  title = "Output",
  titleStyle,
}: WorkflowLogSectionProps) {
  return (
    <div style={workflowSectionCardStyle(false)}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ ...S_SECTION_LABEL, marginBottom: 0, ...titleStyle }}>{title}</div>
        <div style={{ fontSize: 12, color: C.textMuted }}>
          {running ? "Streaming" : "Latest run"}
        </div>
      </div>
      <LogPanel log={log} running={running} />
    </div>
  );
}

interface DependencyPanelProps {
  depGroups: DepGroup[];
}
export function DependencyPanel({ depGroups }: DependencyPanelProps) {
  const [openGroups, setOpenGroups] = useState(() =>
    Object.fromEntries(depGroups.map((g) => [g.path, true])),
  );
  const [filter, setFilter] = useState("all");

  const totalPkgs = depGroups.reduce((sum, group) => sum + group.packages.length, 0);
  const pinnedCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "exact").length,
    0,
  );
  const rangeCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "range").length,
    0,
  );
  const noneCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "none").length,
    0,
  );

  const toggle = (path: string) => setOpenGroups((o) => ({ ...o, [path]: !o[path] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, minHeight: 0 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {[
          {
            key: "all",
            label: `${totalPkgs} total`,
            color: C.textMid,
            bg: C.surfaceAlt,
            border: C.border,
          },
          { key: "exact", ...PIN_META.exact, label: `${pinnedCount} pinned` },
          { key: "range", ...PIN_META.range, label: `${rangeCount} range` },
          { key: "none", ...PIN_META.none, label: `${noneCount} unpinned` },
        ].map((summaryFilter) => (
          <button
            type="button"
            key={summaryFilter.key}
            onClick={() => setFilter(summaryFilter.key)}
            style={{
              ...actionBtn({
                fontSize: 11,
                borderRadius: 99,
                padding: "3px 10px",
                transition: "all 0.12s",
              }),
              color: summaryFilter.color,
              background: filter === summaryFilter.key ? summaryFilter.bg : "transparent",
              border: `1.5px solid ${filter === summaryFilter.key ? summaryFilter.border : C.border}`,
              cursor: "pointer",
            }}
            {...hoverIf(filter !== summaryFilter.key, hoverBg(summaryFilter.bg, "transparent"))}
            {...hoverIf(
              filter !== summaryFilter.key,
              hoverBorderColor(summaryFilter.border, C.border),
            )}
          >
            {summaryFilter.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {depGroups.map((group) => {
          const visiblePkgs =
            filter === "all" ? group.packages : group.packages.filter((p) => p.pinned === filter);
          if (visiblePkgs.length === 0 && filter !== "all") return null;
          const ecoMeta = ECO_META[group.ecosystem] || ECO_META.pip;
          const isOpen = openGroups[group.path] !== false;
          const groupPinned = group.packages.filter((p) => p.pinned === "exact").length;
          const groupUnpinned = group.packages.filter((p) => p.pinned === "none").length;

          return (
            <div
              key={group.path}
              style={{
                border: `1.5px solid ${ecoMeta.color}35`,
                borderRadius: 10,
                overflow: "hidden",
                background: "rgba(255,255,255,0.7)",
              }}
            >
              <button
                type="button"
                onClick={() => toggle(group.path)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 12px",
                  background: `${ecoMeta.color}12`,
                  borderTopWidth: 0,
                  borderLeftWidth: 0,
                  borderRightWidth: 0,
                  borderBottomWidth: isOpen ? 1 : 0,
                  borderBottomStyle: "solid",
                  borderBottomColor: isOpen ? `${ecoMeta.color}25` : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background 0.12s",
                }}
                {...hoverBg(`${ecoMeta.color}1e`, `${ecoMeta.color}12`)}
              >
                <span style={{ display: "flex", color: ecoMeta.color }}>{Ic.file(13)}</span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    color: ecoMeta.color,
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {group.path}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: ecoMeta.color,
                    background: ecoMeta.bg,
                    border: `1px solid ${ecoMeta.color}40`,
                    borderRadius: 99,
                    padding: "1px 6px",
                    fontFamily: F.sans,
                    flexShrink: 0,
                  }}
                >
                  {ecoMeta.label}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    color: "#16a34a",
                    fontFamily: F.mono,
                    flexShrink: 0,
                    marginLeft: 4,
                  }}
                >
                  {groupPinned}✓
                </span>
                {groupUnpinned > 0 && (
                  <span
                    style={{ fontSize: 10, color: "#dc2626", fontFamily: F.mono, flexShrink: 0 }}
                  >
                    {groupUnpinned}✗
                  </span>
                )}
                <span style={{ display: "flex", color: C.textMuted, marginLeft: 4 }}>
                  {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
                </span>
              </button>

              {isOpen && (
                <div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 130px 80px",
                      gap: 0,
                      padding: "4px 12px",
                      background: C.surfaceAlt,
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    {["Package", "Version / Constraint", "Status"].map((h) => (
                      <span
                        key={h}
                        style={{
                          ...S_SECTION_LABEL,
                          fontSize: 10,
                          letterSpacing: 0.8,
                        }}
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                  {(filter === "all" ? group.packages : visiblePkgs).map((pkg, i) => {
                    const pm = PIN_META[pkg.pinned] || PIN_META.none;
                    return (
                      <div
                        key={`${pkg.name}:${pkg.version ?? ""}:${pkg.raw}`}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 130px 80px",
                          gap: 0,
                          padding: "5px 12px",
                          borderBottom: `1px solid ${C.border}`,
                          background: i % 2 === 0 ? "transparent" : "#fafbfd",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 0 }}>
                          {pkg.dev && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.dev.color,
                                background: ECO_META.dev.bg,
                                border: `1px solid ${ECO_META.dev.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              dev
                            </span>
                          )}
                          {pkg.ecosystem === "pip" && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.pip.color,
                                background: ECO_META.pip.bg,
                                border: `1px solid ${ECO_META.pip.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              pip
                            </span>
                          )}
                          <span
                            style={{
                              fontSize: 12,
                              fontFamily: F.mono,
                              color: C.text,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pkg.name}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: pkg.version ? C.textMid : C.textMuted,
                            fontStyle: pkg.version ? "normal" : "italic",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            alignSelf: "center",
                          }}
                        >
                          {pkg.version || "—"}
                        </span>
                        <span style={{ alignSelf: "center" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: pm.color,
                              background: pm.bg,
                              border: `1px solid ${pm.border}`,
                              borderRadius: 99,
                              padding: "1px 6px",
                              fontFamily: F.sans,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pm.label}
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface RuntimeOutputNodeProps {
  expectedOutput: string;
  buildDone: boolean;
  ree: Ree;
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

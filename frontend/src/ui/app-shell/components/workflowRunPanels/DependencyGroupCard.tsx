import type { DepGroup } from "../../../../application/workflow/workflowDependencyAnalysis";
import { ECO_META, PIN_META } from "../../../../application/workflow/workflowDependencyAnalysis";
import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBg, S_SECTION_LABEL } from "../../../theme/theme";

interface DependencyGroupCardProps {
  group: DepGroup;
  filter: string;
  isOpen: boolean;
  onToggle: () => void;
}

export function DependencyGroupCard({ group, filter, isOpen, onToggle }: DependencyGroupCardProps) {
  const visiblePkgs =
    filter === "all" ? group.packages : group.packages.filter((p) => p.pinned === filter);
  if (visiblePkgs.length === 0 && filter !== "all") return null;
  const ecoMeta = ECO_META[group.ecosystem] || ECO_META.pip;
  const groupPinned = group.packages.filter((p) => p.pinned === "exact").length;
  const groupUnpinned = group.packages.filter((p) => p.pinned === "none").length;

  return (
    <div
      style={{
        border: `1.5px solid ${ecoMeta.color}35`,
        borderRadius: 10,
        overflow: "hidden",
        background: "rgba(255,255,255,0.7)",
      }}
    >
      <button
        type="button"
        onClick={onToggle}
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
          <span style={{ fontSize: 10, color: "#dc2626", fontFamily: F.mono, flexShrink: 0 }}>
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
}

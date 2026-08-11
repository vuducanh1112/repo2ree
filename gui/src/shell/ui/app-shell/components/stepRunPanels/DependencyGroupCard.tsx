import {
  type DependencyGroup,
  ECO_LABEL,
  PRESENCE_LABEL,
  STATUS_LABEL,
  tallyByStatus,
} from "@core/evaluate/dependencyPresentation";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  dependencyStatusTone,
  ecosystemTone,
  presenceTone,
  translucent,
} from "@shell/ui/theme/appearance";
import { C, F, hoverBg, S_SECTION_LABEL } from "@shell/ui/theme/theme";

interface DependencyGroupCardProps {
  group: DependencyGroup;
  filter: string;
  isOpen: boolean;
  onToggle: () => void;
}

export function DependencyGroupCard({ group, filter, isOpen, onToggle }: DependencyGroupCardProps) {
  const visiblePkgs =
    filter === "all" ? group.packages : group.packages.filter((p) => p.status === filter);
  if (visiblePkgs.length === 0 && filter !== "all") return null;
  const ecoLine = ecosystemTone(group.ecosystem);
  const tally = tallyByStatus(group.packages);
  // ✓ = resolved (locked + pinned); ✗ = unpinned — the same buckets the
  // filter bar shows, so the two readouts always reconcile by addition.
  const groupResolved = tally.locked + tally.pinned;
  const groupUnpinned = tally.unpinned;

  return (
    <div
      style={{
        border: `1.5px solid ${translucent(ecoLine, 20.8)}`,
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
          background: translucent(ecoLine, 7),
          borderTopWidth: 0,
          borderLeftWidth: 0,
          borderRightWidth: 0,
          borderBottomWidth: isOpen ? 1 : 0,
          borderBottomStyle: "solid",
          borderBottomColor: isOpen ? translucent(ecoLine, 14.5) : "transparent",
          cursor: "pointer",
          textAlign: "left",
          transition: "background 0.12s",
        }}
        {...hoverBg(translucent(ecoLine, 11.8), translucent(ecoLine, 7))}
      >
        <span style={{ display: "flex", color: ecoLine }}>{Ic.file(13)}</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            fontFamily: F.mono,
            color: ecoLine,
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
            color: ecoLine,
            background: ecosystemTone(group.ecosystem, "wash"),
            border: `1px solid ${translucent(ecoLine, 25)}`,
            borderRadius: 99,
            padding: "1px 6px",
            fontFamily: F.sans,
            flexShrink: 0,
          }}
        >
          {ECO_LABEL[group.ecosystem]}
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
          {groupResolved}✓
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
            const statusLabel = STATUS_LABEL[pkg.status];
            return (
              <div
                key={`${pkg.name}:${pkg.version ?? ""}:${pkg.status}`}
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
                  {pkg.scope && (
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: 0.4,
                        color: C.textMuted,
                        border: `1px solid ${C.border}`,
                        borderRadius: 99,
                        padding: "0 5px",
                        flexShrink: 0,
                      }}
                    >
                      {pkg.scope}
                    </span>
                  )}
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
                <span style={{ alignSelf: "center", display: "flex", gap: 4, flexWrap: "wrap" }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: dependencyStatusTone(pkg.status),
                      background: dependencyStatusTone(pkg.status, "wash"),
                      border: `1px solid ${dependencyStatusTone(pkg.status, "edge")}`,
                      borderRadius: 99,
                      padding: "1px 6px",
                      fontFamily: F.sans,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {statusLabel}
                  </span>
                  {pkg.runtimePresence && (
                    <span
                      title={
                        pkg.runtimePresence === "version-mismatch" && pkg.observedVersion
                          ? `runtime has ${pkg.observedVersion}`
                          : undefined
                      }
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: presenceTone(pkg.runtimePresence),
                        background: presenceTone(pkg.runtimePresence, "wash"),
                        border: `1px solid ${presenceTone(pkg.runtimePresence, "edge")}`,
                        borderRadius: 99,
                        padding: "1px 6px",
                        fontFamily: F.sans,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {PRESENCE_LABEL[pkg.runtimePresence]}
                    </span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

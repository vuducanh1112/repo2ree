import {
  type DependencyGroup,
  ECO_LABEL,
  PRESENCE_LABEL,
  STATUS_LABEL,
  tallyByStatus,
} from "@core/evaluate/dependencyPresentation";
import { Ic } from "@shell/ui/shared/components/Icon";
import { ecosystemTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "./DependencyPanel.module.css";

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
      className={styles.group}
      style={cssVars({
        "--eco-line": ecoLine,
        "--eco-wash": ecosystemTone(group.ecosystem, "wash"),
      })}
    >
      <button type="button" onClick={onToggle} aria-expanded={isOpen} className={styles.groupHead}>
        <span aria-hidden className={styles.groupIcon}>
          {Ic.file(13)}
        </span>
        <span className={styles.groupPath}>{group.path}</span>
        <span className={styles.ecosystem}>{ECO_LABEL[group.ecosystem]}</span>
        <span className={styles.tally} data-kind="resolved">
          {groupResolved}✓
        </span>
        {groupUnpinned > 0 && (
          <span className={styles.tally} data-kind="unpinned">
            {groupUnpinned}✗
          </span>
        )}
        <span aria-hidden className={styles.groupChevron}>
          {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
        </span>
      </button>

      {isOpen && (
        <div>
          <div className={styles.tableHead}>
            {["Package", "Version / Constraint", "Status"].map((h) => (
              <span key={h} className={styles.columnLabel}>
                {h}
              </span>
            ))}
          </div>
          {(filter === "all" ? group.packages : visiblePkgs).map((pkg, i) => {
            const statusLabel = STATUS_LABEL[pkg.status];
            return (
              <div
                key={`${pkg.name}:${pkg.version ?? ""}:${pkg.status}`}
                className={styles.packageRow}
                data-odd={i % 2 === 1 ? true : undefined}
              >
                <div className={styles.packageName}>
                  <span className={styles.packageLabel}>{pkg.name}</span>
                  {pkg.scope && <span className={styles.scope}>{pkg.scope}</span>}
                </div>
                <span className={styles.version} data-unset={pkg.version ? undefined : true}>
                  {pkg.version || "—"}
                </span>
                <span className={styles.verdicts}>
                  <span className={styles.verdict} data-status={pkg.status}>
                    {statusLabel}
                  </span>
                  {pkg.runtimePresence && (
                    <span
                      title={
                        pkg.runtimePresence === "version-mismatch" && pkg.observedVersion
                          ? `runtime has ${pkg.observedVersion}`
                          : undefined
                      }
                      className={styles.verdict}
                      data-presence={pkg.runtimePresence}
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

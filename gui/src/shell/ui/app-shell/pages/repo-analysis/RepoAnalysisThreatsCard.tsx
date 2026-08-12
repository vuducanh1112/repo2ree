import type { Threat, ThreatCategory } from "@core/evaluate/Threat";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import { CardHeader } from "./RepoAnalysisCardHeader";
import styles from "./RepoAnalysisPage.module.css";

const THREAT_DIMENSIONS: { category: ThreatCategory; label: string }[] = [
  { category: "dependency", label: "Dependency declaration" },
  { category: "environment", label: "Environment capture" },
  { category: "machine", label: "Machine capture" },
];

function ThreatRow({ threat }: { threat: Threat }) {
  return (
    <div
      className={styles.threat}
      data-severity={threat.severity}
      data-blocking={threat.blocking || undefined}
    >
      <div className={styles.threatHead}>
        <span className={styles.severity}>{threat.severity}</span>
        <span className={styles.threatCategory}>{threat.category}</span>
        <span className={styles.threatTitle}>{threat.title}</span>
        {threat.blocking && (
          <span className={styles.blocking}>{Ic.info(11)} blocking next level</span>
        )}
      </div>

      <div className={styles.threatDetail}>{threat.detail}</div>

      {threat.affected.length > 0 && (
        <div className={styles.affected}>
          {threat.affected.slice(0, 8).map((entry) => (
            <span key={entry} className={styles.affectedItem}>
              {entry}
            </span>
          ))}
          {threat.affected.length > 8 && (
            <span className={styles.affectedMore}>+{threat.affected.length - 8} more</span>
          )}
        </div>
      )}

      <div className={styles.remedy}>
        <span aria-hidden className={styles.remedyIcon}>
          {Ic.check(12)}
        </span>
        <span>{threat.remediation}</span>
      </div>
    </div>
  );
}

export function RepoAnalysisThreatsCard({
  hasReport,
  threats,
  loading,
}: {
  hasReport: boolean;
  threats: Threat[];
  loading: boolean;
}) {
  const sorted = threats; // backend already sorts blocking-first, then by severity

  return (
    <Surface>
      <CardHeader
        label="Reproducibility Threats"
        hint={
          !hasReport
            ? "Awaiting run"
            : loading
              ? "Loading…"
              : sorted.length > 0
                ? `${sorted.length} found`
                : "None detected"
        }
      />

      {!hasReport ? (
        <div className={styles.placeholder}>
          Run Evaluate to surface threats to reproducibility.
        </div>
      ) : sorted.length === 0 ? (
        <div className={styles.clear}>
          <span aria-hidden>{Ic.check(14)}</span>
          {loading ? "Loading report…" : "No reproducibility threats detected."}
        </div>
      ) : (
        <div className={styles.dimensions}>
          {THREAT_DIMENSIONS.map(({ category, label }) => {
            const inDimension = sorted.filter((threat) => threat.category === category);
            if (inDimension.length === 0) return null;
            return (
              <div key={category} className={styles.dimension}>
                <div className={styles.dimensionLabel}>{label}</div>
                {inDimension.map((threat) => (
                  <ThreatRow key={threat.id} threat={threat} />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </Surface>
  );
}

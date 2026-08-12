import { GlassPanel } from "@shell/ui/app-shell/components/GlassPageShell";
import { Ic } from "@shell/ui/shared/components/Icon";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "./ExperimentsPage.module.css";

export interface ExperimentSuggestion {
  name: string;
  description: string;
  command: string;
}

const EXPERIMENT_SUGGESTIONS: ExperimentSuggestion[] = [
  {
    name: "pytest",
    description: "Run the project's pytest suite.",
    command: "pytest -q",
  },
  {
    name: "import-smoke",
    description: "Import the main package to verify install.",
    command: 'python -c "import {{package}}"',
  },
  {
    name: "make-test",
    description: "Invoke the project's Makefile test target.",
    command: "make test",
  },
  {
    name: "run-script",
    description: "Execute the project's main entry script.",
    command: "bash run.sh",
  },
];

export function ExperimentsCoverageAside({
  total,
  withName,
  withCommand,
  withDescription,
  withVerify,
  withRuntimeEstimate,
  withResourceEstimates,
}: {
  total: number;
  withName: number;
  withCommand: number;
  withDescription: number;
  withVerify: number;
  withRuntimeEstimate: number;
  withResourceEstimates: number;
}) {
  const incomplete = total - Math.min(withName, withCommand, withVerify);
  const allComplete = total > 0 && incomplete === 0;
  return (
    <GlassPanel density="compact">
      <div className={styles.asideHead}>
        <span aria-hidden className={styles.asideIcon}>
          {Ic.layers(18)}
        </span>
        <h3 className={styles.asideTitle}>Coverage</h3>
      </div>
      {total === 0 ? (
        <div className={styles.asideCopy}>
          No experiments yet. Add one to start tracking coverage.
        </div>
      ) : (
        <div className={styles.coverage}>
          <CoverageRow label="Experiments" value={total} total={total} />
          <CoverageRow label="With name" value={withName} total={total} />
          <CoverageRow label="With command" value={withCommand} total={total} />
          <CoverageRow label="With description" value={withDescription} total={total} />
          <CoverageRow label="With verify script" value={withVerify} total={total} />
          <CoverageRow label="With runtime est." value={withRuntimeEstimate} total={total} />
          <CoverageRow label="With resource est." value={withResourceEstimates} total={total} />
          {!allComplete && (
            <div className={styles.tally}>
              <span aria-hidden className={styles.tallyIcon}>
                {Ic.info(12)}
              </span>
              {incomplete} still need the core runnable fields or a verify script.
            </div>
          )}
          {allComplete && (
            <div className={styles.tally} data-complete>
              <span aria-hidden className={styles.tallyIcon}>
                {Ic.check(12)}
              </span>
              All experiments are complete.
            </div>
          )}
        </div>
      )}
    </GlassPanel>
  );
}

function CoverageRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((value / total) * 100);
  return (
    <div className={styles.coverageRow}>
      <div className={styles.coverageHead}>
        <span>{label}</span>
        <span className={styles.coverageCount}>
          {value}/{total}
        </span>
      </div>
      <div className={styles.track}>
        <div className={styles.fill} style={cssVars({ "--coverage-pct": `${pct}%` })} />
      </div>
    </div>
  );
}

export function ExperimentsSuggestionsAside({
  locked,
  onAdd,
}: {
  locked: boolean;
  onAdd: (suggestion: ExperimentSuggestion) => void;
}) {
  return (
    <GlassPanel density="compact">
      <div className={styles.asideHead} data-tight>
        <span aria-hidden className={styles.asideIcon}>
          {Ic.plus(18)}
        </span>
        <h3 className={styles.asideTitle}>Quick add</h3>
      </div>
      <div className={styles.asideHint}>
        Common verifications — click to add a prefilled experiment.
      </div>
      <div className={styles.suggestions}>
        {EXPERIMENT_SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion.name}
            type="button"
            disabled={locked}
            onClick={() => onAdd(suggestion)}
            title={suggestion.command}
            className={styles.suggestion}
          >
            {suggestion.name}
          </button>
        ))}
      </div>
    </GlassPanel>
  );
}

export function ExperimentsAboutAside() {
  return (
    <GlassPanel density="compact">
      <div className={styles.asideHead} data-tight>
        <span aria-hidden className={styles.asideIcon}>
          {Ic.info(18)}
        </span>
        <h3 className={styles.asideTitle}>About experiments</h3>
      </div>
      <div className={styles.asideCopy}>
        Experiments are run inside the assembled REE, then their verify script checks the claimed
        results. Runtime and resource estimates help future users plan how expensive those checks
        will be.
      </div>
    </GlassPanel>
  );
}

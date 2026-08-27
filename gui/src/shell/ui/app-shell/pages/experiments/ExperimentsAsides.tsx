import { Ic } from "@shell/ui/shared/components/Icon";
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

/**
 * Whether the declared experiments are runnable, as one line. This used to be
 * seven stacked meters in a side column — one of which ("Experiments") was
 * value-over-itself and so always full. The per-field detail belongs to the
 * experiment it describes, on its card; the aggregate only ever had to say
 * whether anything still needs work.
 */
export function ExperimentsCoverageTally({
  total,
  withName,
  withCommand,
  withVerify,
}: {
  total: number;
  withName: number;
  withCommand: number;
  withVerify: number;
}) {
  if (total === 0) return null;
  const incomplete = total - Math.min(withName, withCommand, withVerify);
  const complete = incomplete === 0;
  return (
    <span className={styles.tally} data-complete={complete || undefined}>
      <span aria-hidden className={styles.tallyIcon}>
        {complete ? Ic.check(12) : Ic.info(12)}
      </span>
      {complete
        ? "All experiments are complete."
        : `${incomplete} still need the core runnable fields or a verify script.`}
    </span>
  );
}

/** Prefilled starting points, offered where an experiment is added. */
export function ExperimentQuickAdd({
  locked,
  onAdd,
}: {
  locked: boolean;
  onAdd: (suggestion: ExperimentSuggestion) => void;
}) {
  return (
    <div className={styles.quickAdd}>
      <span className={styles.quickAddLabel}>Quick add</span>
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
    </div>
  );
}

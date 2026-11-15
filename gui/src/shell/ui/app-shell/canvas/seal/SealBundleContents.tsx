import { PAGE } from "@core/app-shell/pages";
import { Toggle } from "@shell/ui/shared/components/Toggle";
import { stageTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "../SealContent.module.css";

interface InclusionRow {
  label: string;
  available: boolean;
  included: boolean;
  tintLine: string;
  tintInk: string;
  onToggle: () => void;
  /** What the row says when there is nothing to include. */
  unavailable?: string;
}

interface SealBundleContentsProps {
  sourceAvailable: boolean;
  experimentEnvironmentAvailable: boolean;
  resultsAvailable: boolean;
  workingEnvironmentAvailable: boolean;
  includeSource: boolean;
  includeExperimentEnvironment: boolean;
  includeResults: boolean;
  includeWorkingEnvironment: boolean;
  onToggleSource: () => void;
  onToggleExperimentEnvironment: () => void;
  onToggleResults: () => void;
  onToggleWorkingEnvironment: () => void;
}

function Row({
  label,
  available,
  included,
  tintLine,
  tintInk,
  onToggle,
  unavailable = "Not in workspace",
}: InclusionRow) {
  const on = available && included;
  return (
    <div
      className={styles.inclusionRow}
      data-unavailable={available ? undefined : true}
      style={cssVars({ "--seal-ink": tintInk })}
    >
      <div className={styles.inclusionLabels}>
        <span className={styles.inclusionName}>{label}</span>
        <span className={styles.inclusionState}>
          {!available ? unavailable : on ? "Bundled into the archive" : "Excluded"}
        </span>
      </div>
      <div className={styles.inclusionControl}>
        <span className={styles.inclusionVerb} data-on={on || undefined}>
          {on ? "Included" : "Include"}
        </span>
        <Toggle
          on={on}
          disabled={!available}
          ariaLabel={`Include ${label.toLowerCase()} in bundle`}
          tint={tintLine}
          onChange={onToggle}
        />
      </div>
    </div>
  );
}

/** What the sealed archive carries. Each row is tinted by the step that
 *  produced the content, so the choice reads back to where it came from. */
export function SealBundleContents({
  sourceAvailable,
  experimentEnvironmentAvailable,
  resultsAvailable,
  workingEnvironmentAvailable,
  includeSource,
  includeExperimentEnvironment,
  includeResults,
  includeWorkingEnvironment,
  onToggleSource,
  onToggleExperimentEnvironment,
  onToggleResults,
  onToggleWorkingEnvironment,
}: SealBundleContentsProps) {
  return (
    <div className={styles.inclusion}>
      <Row
        label="Source"
        available={sourceAvailable}
        included={includeSource}
        tintLine={stageTone(PAGE.SOURCE)}
        tintInk={stageTone(PAGE.SOURCE, "ink")}
        onToggle={onToggleSource}
      />
      <Row
        label="Experiment environment"
        available={experimentEnvironmentAvailable}
        included={includeExperimentEnvironment}
        tintLine={stageTone(PAGE.BUILD_EXPERIMENT_ENVIRONMENT)}
        tintInk={stageTone(PAGE.BUILD_EXPERIMENT_ENVIRONMENT, "ink")}
        onToggle={onToggleExperimentEnvironment}
      />
      <Row
        label="Working environment image"
        available={workingEnvironmentAvailable}
        included={includeWorkingEnvironment}
        tintLine={stageTone(PAGE.BUILD_EXPERIMENT_ENVIRONMENT)}
        tintInk={stageTone(PAGE.BUILD_EXPERIMENT_ENVIRONMENT, "ink")}
        onToggle={onToggleWorkingEnvironment}
        unavailable="No image declared: the scripts run on the lab's own machine"
      />
      <Row
        label="Results"
        available={resultsAvailable}
        included={includeResults}
        tintLine={stageTone(PAGE.EXPERIMENTS)}
        tintInk={stageTone(PAGE.EXPERIMENTS, "ink")}
        onToggle={onToggleResults}
      />
    </div>
  );
}

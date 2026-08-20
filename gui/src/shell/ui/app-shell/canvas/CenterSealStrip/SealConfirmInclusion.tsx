import { PAGE } from "@core/app-shell/pages";
import { Toggle } from "@shell/ui/shared/components/Toggle";
import { stageTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "./CenterSealStrip.module.css";

interface InclusionRow {
  label: string;
  available: boolean;
  included: boolean;
  tintLine: string;
  tintInk: string;
  onToggle: () => void;
}

interface SealConfirmInclusionProps {
  sourceAvailable: boolean;
  runtimeAvailable: boolean;
  resultsAvailable: boolean;
  includeSource: boolean;
  includeRuntime: boolean;
  includeResults: boolean;
  onToggleSource: () => void;
  onToggleRuntime: () => void;
  onToggleResults: () => void;
}

function Row({ label, available, included, tintLine, tintInk, onToggle }: InclusionRow) {
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
          {!available ? "Not in workspace" : on ? "Bundled into the archive" : "Excluded"}
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

export function SealConfirmInclusion({
  sourceAvailable,
  runtimeAvailable,
  resultsAvailable,
  includeSource,
  includeRuntime,
  includeResults,
  onToggleSource,
  onToggleRuntime,
  onToggleResults,
}: SealConfirmInclusionProps) {
  return (
    <div className={styles.inclusion}>
      <span className={styles.inclusionHeading}>Bundle contents</span>
      <Row
        label="Source"
        available={sourceAvailable}
        included={includeSource}
        tintLine={stageTone(PAGE.SOURCE)}
        tintInk={stageTone(PAGE.SOURCE, "ink")}
        onToggle={onToggleSource}
      />
      <Row
        label="Runtime"
        available={runtimeAvailable}
        included={includeRuntime}
        tintLine={stageTone(PAGE.BUILD)}
        tintInk={stageTone(PAGE.BUILD, "ink")}
        onToggle={onToggleRuntime}
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

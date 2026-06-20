import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgStyles, lgSuggestionButton } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

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
  withOutputs,
  withRuntimeEstimate,
  withResourceEstimates,
}: {
  total: number;
  withName: number;
  withCommand: number;
  withDescription: number;
  withOutputs: number;
  withRuntimeEstimate: number;
  withResourceEstimates: number;
}) {
  const incomplete = total - Math.min(withName, withCommand, withOutputs);
  const allComplete = total > 0 && incomplete === 0;
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.layers(18)}</span>
        <h3 style={{ margin: 0, fontSize: 14, color: lgColors.text }}>Coverage</h3>
      </div>
      {total === 0 ? (
        <div style={{ fontSize: 12, color: lgColors.textMid, lineHeight: 1.5 }}>
          No experiments yet. Add one to start tracking coverage.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <CoverageRow label="Experiments" value={total} total={total} />
          <CoverageRow label="With name" value={withName} total={total} />
          <CoverageRow label="With command" value={withCommand} total={total} />
          <CoverageRow label="With description" value={withDescription} total={total} />
          <CoverageRow label="With outputs" value={withOutputs} total={total} />
          <CoverageRow label="With runtime est." value={withRuntimeEstimate} total={total} />
          <CoverageRow label="With resource est." value={withResourceEstimates} total={total} />
          {!allComplete && (
            <div
              style={{
                marginTop: 4,
                fontSize: 11,
                color: lgColors.warning,
                background: "rgba(254, 249, 195, 0.7)",
                border: "1px solid rgba(245, 158, 11, 0.45)",
                borderRadius: 7,
                padding: "6px 9px",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ display: "flex" }}>{Ic.info(12)}</span>
              {incomplete} still need the core runnable fields or expected outputs.
            </div>
          )}
          {allComplete && (
            <div
              style={{
                marginTop: 4,
                fontSize: 11,
                color: lgColors.success,
                background: "rgba(220, 252, 231, 0.78)",
                border: "1px solid rgba(34, 197, 94, 0.42)",
                borderRadius: 7,
                padding: "6px 9px",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ display: "flex" }}>{Ic.check(12)}</span>
              All experiments are complete.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function CoverageRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((value / total) * 100);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: lgColors.textMid,
        }}
      >
        <span>{label}</span>
        <span style={{ fontFamily: F.mono, color: lgColors.text, fontWeight: 700 }}>
          {value}/{total}
        </span>
      </div>
      <div style={lgStyles.progressTrack}>
        <div style={{ ...lgStyles.progressFill, width: `${pct}%` }} />
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
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.plus(18)}</span>
        <h3 style={{ margin: 0, fontSize: 14, color: lgColors.text }}>Quick add</h3>
      </div>
      <div style={{ fontSize: 11, color: lgColors.textMuted, marginBottom: 10 }}>
        Common verifications — click to add a prefilled experiment.
      </div>
      <div style={lgStyles.suggestionWrap}>
        {EXPERIMENT_SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion.name}
            type="button"
            disabled={locked}
            onClick={() => onAdd(suggestion)}
            title={suggestion.command}
            style={{
              ...lgSuggestionButton(),
              opacity: locked ? 0.5 : 1,
              cursor: locked ? "not-allowed" : "pointer",
            }}
          >
            {suggestion.name}
          </button>
        ))}
      </div>
    </section>
  );
}

export function ExperimentsAboutAside() {
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.info(18)}</span>
        <h3 style={{ margin: 0, fontSize: 14, color: lgColors.text }}>About experiments</h3>
      </div>
      <div style={{ fontSize: 12, color: lgColors.textMid, lineHeight: 1.5 }}>
        Experiments are run inside the assembled REE to confirm it reproduces the expected outputs.
        Runtime and resource estimates help future users plan how expensive those checks will be.
      </div>
    </section>
  );
}

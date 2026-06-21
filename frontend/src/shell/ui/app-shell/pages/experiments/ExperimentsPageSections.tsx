import type { ExperimentOutputResult } from "@core/execution/ExperimentRun";
import type {
  ExpectedOutput,
  ExperimentResourceEstimates,
  OutputMatch,
  OutputSource,
  ReeExperiment,
} from "@core/ree/ReeSpec";
import type { LogEntry } from "@core/ree/ReeTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgActionButton,
  lgColors,
  lgGlassButton,
  lgInput,
  lgNextButton,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import type React from "react";
import { LogPanel } from "../../components/logPanel";
import { RunActionButton } from "../../components/RunActionButton";
import { experimentValidation, expId } from "./experimentsPageHelpers";
import { type RunState, TERMINAL_STATUSES } from "./useExperimentRun";

// The experiments page is composed from three modules; re-exported here so the
// page keeps a single import surface.
export { ExperimentCardList } from "./ExperimentCardList";
export {
  type ExperimentSuggestion,
  ExperimentsAboutAside,
  ExperimentsCoverageAside,
  ExperimentsSuggestionsAside,
} from "./ExperimentsAsides";

// ================================================
// Detail view
// ================================================

export function ExperimentDetail({
  experiment,
  index,
  otherNames,
  locked,
  onUpdate,
  onBack,
  runState,
}: {
  experiment: ReeExperiment;
  index: number;
  otherNames: string[];
  locked: boolean;
  onUpdate: (patch: Partial<ReeExperiment>) => void;
  onBack: () => void;
  runState: RunState | null;
}) {
  const { trimmedName, isDuplicateName, isInvalidName, canRun } = experimentValidation(
    experiment,
    otherNames,
  );

  return (
    <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
      <DetailBreadcrumb index={index} onBack={onBack} />

      <div style={{ ...lgStyles.sectionBody, display: "flex", flexDirection: "column", gap: 18 }}>
        <DetailField label="Name" required>
          <input
            disabled={locked}
            value={experiment.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="smoke-test"
            style={{
              ...lgInput(locked),
              ...(isDuplicateName || isInvalidName
                ? { borderColor: "rgba(239, 68, 68, 0.7)" }
                : {}),
            }}
          />
          {isDuplicateName && (
            <span style={{ fontSize: 11, color: lgColors.required, marginTop: 2 }}>
              Another experiment already uses this name.
            </span>
          )}
          {!isDuplicateName && isInvalidName && (
            <span style={{ fontSize: 11, color: lgColors.required, marginTop: 2 }}>
              Use only letters, digits, spaces, '.', '_' and '-'.
            </span>
          )}
        </DetailField>

        <DetailField label="Description" help="What this experiment verifies in the REE.">
          <textarea
            disabled={locked}
            value={experiment.description}
            onChange={(e) => onUpdate({ description: e.target.value })}
            placeholder="Imports the main package and runs the smoke suite."
            rows={3}
            style={{ ...lgInput(locked), resize: "vertical", minHeight: 84, lineHeight: 1.5 }}
          />
        </DetailField>

        <DetailField label="Command" help="Executed inside the assembled runtime.">
          <input
            disabled={locked}
            value={experiment.command}
            onChange={(e) => onUpdate({ command: e.target.value })}
            placeholder="pytest tests/smoke -q"
            style={{ ...lgInput(locked), fontFamily: F.mono, fontSize: 13 }}
          />
        </DetailField>

        <DetailField
          label="Runtime estimate"
          help="Expected wall-clock duration for a typical successful run."
        >
          <input
            disabled={locked}
            value={experiment.runtime_estimate}
            onChange={(e) => onUpdate({ runtime_estimate: e.target.value })}
            placeholder="5-10 min"
            style={{ ...lgInput(locked), fontFamily: F.mono, fontSize: 13 }}
          />
        </DetailField>

        <ResourceEstimatesEditor
          estimates={experiment.resource_estimates}
          locked={locked}
          onChange={(resource_estimates) => onUpdate({ resource_estimates })}
        />

        <OutputsEditor
          outputs={experiment.outputs}
          locked={locked}
          onChange={(outputs) => onUpdate({ outputs })}
        />

        {runState && <RunResultPanel runState={runState} />}
      </div>

      <div style={lgStyles.footer}>
        <span style={{ color: lgColors.textMuted, fontSize: 12 }}>
          {!locked && trimmedName === ""
            ? "A name is required."
            : !locked && isDuplicateName
              ? "Fix the duplicate name to continue."
              : !locked && isInvalidName
                ? "Fix the invalid name to continue."
                : "Edits save automatically."}
        </span>
        <button
          type="button"
          onClick={onBack}
          disabled={!locked && !canRun}
          style={{
            ...lgNextButton(),
            ...(!locked && !canRun ? { opacity: 0.45, cursor: "not-allowed" } : {}),
          }}
        >
          {Ic.check(15)} Save & back to catalog
        </button>
      </div>
    </section>
  );
}

function DetailBreadcrumb({ index, onBack }: { index: number; onBack: () => void }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 18px",
        borderBottom: "1px solid rgba(125, 211, 252, 0.4)",
        background: "rgba(255, 255, 255, 0.55)",
      }}
    >
      <button
        type="button"
        onClick={onBack}
        style={{
          ...lgGlassButton(),
          padding: "6px 12px",
          fontSize: 12,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        {Ic.arrowLeft(13)} Experiments
      </button>
      <span style={{ color: lgColors.textMuted }}>/</span>
      <span
        style={{
          fontFamily: F.mono,
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: "0.08em",
          color: lgColors.cyan,
          border: "1px solid rgba(14, 165, 233, 0.32)",
          background: "rgba(240, 249, 255, 0.85)",
          borderRadius: 6,
          padding: "3px 8px",
        }}
      >
        {expId(index)}
      </span>
    </div>
  );
}

// The selected experiment's Run / Snapshot / Delete controls, rendered in the
// page header's top-right (like the Build Runtime page's run controls) rather
// than inside the detail panel.
export function ExperimentHeaderActions({
  locked,
  canRun,
  canSnapshot,
  isRunning,
  onRun,
  onSnapshot,
  onRemove,
}: {
  locked: boolean;
  canRun: boolean;
  canSnapshot: boolean;
  isRunning: boolean;
  onRun: () => void;
  onSnapshot: () => void;
  onRemove: () => void;
}) {
  const runTitle = canRun
    ? "Verify outputs against recorded expectations"
    : "Add a unique name and command before running";
  const snapshotTitle = locked
    ? "Unlock the draft to update baselines"
    : canRun
      ? "Run command and capture outputs as sha256 baselines"
      : "Add a unique name and command before snapshotting";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
      <RunActionButton
        label={isRunning ? "Running…" : "Run"}
        running={isRunning}
        disabled={!canRun || isRunning}
        iconSize={12}
        title={runTitle}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          border: "1px solid rgba(79, 70, 229, 0.45)",
          background:
            canRun && !isRunning ? "rgba(238, 242, 255, 0.9)" : "rgba(241, 245, 249, 0.72)",
          color: canRun && !isRunning ? lgColors.blue : lgColors.textMuted,
          padding: "6px 14px",
          borderRadius: 8,
          fontWeight: 700,
          fontSize: 12,
          cursor: canRun && !isRunning ? "pointer" : "not-allowed",
          opacity: canRun && !isRunning ? 1 : 0.45,
        }}
        onRun={onRun}
      />
      <button
        type="button"
        disabled={!canSnapshot || isRunning}
        title={snapshotTitle}
        onClick={onSnapshot}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          border: "1px solid rgba(34, 197, 94, 0.45)",
          background:
            canSnapshot && !isRunning ? "rgba(240, 253, 244, 0.9)" : "rgba(241, 245, 249, 0.72)",
          color: canSnapshot && !isRunning ? lgColors.success : lgColors.textMuted,
          padding: "6px 14px",
          borderRadius: 8,
          fontWeight: 700,
          fontSize: 12,
          cursor: canSnapshot && !isRunning ? "pointer" : "not-allowed",
          opacity: canSnapshot && !isRunning ? 1 : 0.45,
        }}
      >
        {Ic.refresh(12)} Snapshot
      </button>
      {!locked && (
        <button
          type="button"
          onClick={onRemove}
          style={{
            ...lgActionButton("danger"),
            width: "auto",
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 700,
            gap: 6,
          }}
        >
          {Ic.x(12)} Delete
        </button>
      )}
    </div>
  );
}

function DetailField({
  label,
  required,
  help,
  children,
}: {
  label: string;
  required?: boolean;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={lgStyles.fieldFrame}>
      <span style={lgStyles.label}>
        {label}
        {required && <span style={{ color: lgColors.required }}>*</span>}
      </span>
      {children}
      {help && <span style={lgStyles.helper}>{help}</span>}
    </div>
  );
}

// ================================================
// Run result panel
// ================================================

function RunResultPanel({ runState }: { runState: RunState }) {
  const isTerminal = TERMINAL_STATUSES.includes(runState.status);
  const { outputs } = runState;
  const logEntry: LogEntry | null =
    runState.logLines.length > 0 ? { lines: runState.logLines, ts: runState.startedAt } : null;

  const headerColor =
    outputs?.verdict === "pass"
      ? lgColors.success
      : outputs?.verdict === "fail" || runState.status === "failed"
        ? lgColors.required
        : lgColors.textMuted;

  const headerBg =
    outputs?.verdict === "pass"
      ? "rgba(220, 252, 231, 0.7)"
      : outputs?.verdict === "fail" || runState.status === "failed"
        ? "rgba(254, 226, 226, 0.7)"
        : "rgba(248, 250, 252, 0.7)";

  return (
    <div style={lgStyles.fieldFrame}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={lgStyles.label}>
          {runState.mode === "snapshot" ? "Snapshot result" : "Run result"}
        </span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: headerColor,
            background: headerBg,
            border: `1px solid ${headerColor}44`,
            borderRadius: 99,
            padding: "2px 8px",
            fontFamily: F.mono,
            textTransform: "uppercase",
          }}
        >
          {!isTerminal ? runState.status : (outputs?.verdict ?? runState.status)}
        </span>
      </div>

      {!isTerminal && (
        <div
          style={{
            color: lgColors.textMuted,
            fontSize: 12,
            textAlign: "center",
            padding: "10px 0",
          }}
        >
          {Ic.loader(13)} Running experiment…
        </div>
      )}

      {isTerminal && outputs && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {outputs.mode === "snapshot" ? (
            <div
              style={{
                fontSize: 12,
                color: outputs.snapshotApplied ? lgColors.success : lgColors.required,
              }}
            >
              {outputs.snapshotApplied
                ? (outputs.snapshotMessage ??
                  `${outputs.snapshotCount ?? 0} baseline(s) saved (sha256). Outputs updated.`)
                : (outputs.snapshotMessage ?? "Snapshot failed — command did not exit 0.")}
            </div>
          ) : outputs.outputResults && outputs.outputResults.length > 0 ? (
            outputs.outputResults.map((r: ExperimentOutputResult) => (
              <div
                key={r.sourceKey}
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                  fontSize: 12,
                  padding: "6px 10px",
                  borderRadius: 7,
                  background: r.passed ? "rgba(220, 252, 231, 0.5)" : "rgba(254, 226, 226, 0.5)",
                  border: `1px solid ${r.passed ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
                }}
              >
                <span
                  style={{
                    color: r.passed ? lgColors.success : lgColors.required,
                    flexShrink: 0,
                  }}
                >
                  {r.passed ? Ic.check(13) : Ic.x(13)}
                </span>
                <div>
                  <span style={{ fontFamily: F.mono, fontWeight: 700, color: lgColors.textMuted }}>
                    {r.sourceKey}
                  </span>
                  <span style={{ color: lgColors.textMuted, margin: "0 5px" }}>·</span>
                  <span style={{ color: lgColors.textMuted }}>{r.detail}</span>
                </div>
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: lgColors.textMuted }}>
              {outputs.verdict === "pass"
                ? "Command exited 0 — no output assertions declared."
                : `Command failed (exit code ${outputs.exitCode ?? "?"}).`}
            </div>
          )}
        </div>
      )}

      {isTerminal && !outputs && (
        <div style={{ fontSize: 12, color: lgColors.required }}>
          Run {runState.status} — no output data available.
        </div>
      )}

      <div style={{ marginTop: 10, height: 320, display: "flex", flexDirection: "column" }}>
        <LogPanel log={logEntry} running={!isTerminal} />
      </div>
    </div>
  );
}

// ================================================
// Resource estimates editor
// ================================================

function ResourceEstimatesEditor({
  estimates,
  locked,
  onChange,
}: {
  estimates: ExperimentResourceEstimates;
  locked: boolean;
  onChange: (estimates: ExperimentResourceEstimates) => void;
}) {
  const updateField = (field: keyof ExperimentResourceEstimates, value: string) => {
    onChange({ ...estimates, [field]: value });
  };

  const resourceFields: Array<{
    field: keyof ExperimentResourceEstimates;
    label: string;
    placeholder: string;
  }> = [
    { field: "cpu", label: "CPU", placeholder: "4 vCPU sustained" },
    { field: "memory", label: "Memory", placeholder: "8 GB RAM peak" },
    { field: "gpu", label: "GPU", placeholder: "None or 1x T4" },
    { field: "storage", label: "Storage", placeholder: "2 GB scratch output" },
    { field: "network", label: "Network", placeholder: "Offline after setup" },
  ];

  return (
    <div style={lgStyles.fieldFrame}>
      <span style={lgStyles.label}>Resource estimates</span>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 10,
        }}
      >
        {resourceFields.map(({ field, label, placeholder }) => (
          <label
            key={field}
            style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, color: lgColors.textMuted }}>
              {label}
            </span>
            <input
              disabled={locked}
              value={estimates[field]}
              onChange={(e) => updateField(field, e.target.value)}
              placeholder={placeholder}
              style={{ ...lgInput(locked), fontFamily: F.mono, fontSize: 12 }}
            />
          </label>
        ))}
      </div>
      <span style={lgStyles.helper}>
        Capture the expected compute footprint so others can budget time and infrastructure.
      </span>
    </div>
  );
}

// ================================================
// Expected outputs editor
// ================================================

function OutputsEditor({
  outputs,
  locked,
  onChange,
}: {
  outputs: ExpectedOutput[] | undefined;
  locked: boolean;
  onChange: (outputs: ExpectedOutput[]) => void;
}) {
  const list = outputs ?? [];

  const addOutput = () => {
    onChange([...list, { source: { kind: "stdout" }, match: { mode: "contains", value: "" } }]);
  };

  const removeOutput = (i: number) => {
    onChange(list.filter((_, idx) => idx !== i));
  };

  const updateOutput = (i: number, updated: ExpectedOutput) => {
    onChange(list.map((o, idx) => (idx === i ? updated : o)));
  };

  return (
    <div style={lgStyles.fieldFrame}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={lgStyles.label}>Expected outputs</span>
        {!locked && (
          <button
            type="button"
            onClick={addOutput}
            style={{
              ...lgGlassButton(),
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 700,
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            {Ic.plus(11)} Add
          </button>
        )}
      </div>
      {list.length === 0 ? (
        <div
          style={{
            border: "1px dashed rgba(148, 163, 184, 0.45)",
            borderRadius: 9,
            padding: "16px",
            background: "rgba(248, 250, 252, 0.6)",
            color: lgColors.textMuted,
            fontSize: 12,
            textAlign: "center",
            lineHeight: 1.5,
          }}
        >
          No expected outputs defined. Add one to make this experiment falsifiable.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {list.map((output, i) => (
            <OutputRow
              key={`out-${String(i)}`}
              output={output}
              locked={locked}
              onUpdate={(updated) => updateOutput(i, updated)}
              onRemove={() => removeOutput(i)}
            />
          ))}
        </div>
      )}
      <span style={lgStyles.helper}>
        Declare what this command must produce for the experiment to be considered reproduced.
      </span>
    </div>
  );
}

function OutputRow({
  output,
  locked,
  onUpdate,
  onRemove,
}: {
  output: ExpectedOutput;
  locked: boolean;
  onUpdate: (updated: ExpectedOutput) => void;
  onRemove: () => void;
}) {
  const { source, match } = output;

  const setSourceKind = (kind: OutputSource["kind"]) => {
    const newSource: OutputSource =
      kind === "file"
        ? { kind: "file", path: source.kind === "file" ? source.path : "" }
        : { kind };
    onUpdate({ source: newSource, match });
  };

  const setPath = (path: string) => {
    if (source.kind !== "file") return;
    onUpdate({ source: { kind: "file", path }, match });
  };

  const setMatchMode = (mode: OutputMatch["mode"]) => {
    const next: OutputMatch =
      mode === "numeric"
        ? { mode, value: match.value, epsilon: match.mode === "numeric" ? match.epsilon : 1e-6 }
        : { mode, value: match.value };
    onUpdate({ source, match: next });
  };

  const setMatchValue = (value: string) => {
    onUpdate({ source, match: { ...match, value } });
  };

  const setEpsilon = (raw: string) => {
    if (match.mode !== "numeric") return;
    const parsed = Number.parseFloat(raw);
    if (!Number.isNaN(parsed)) onUpdate({ source, match: { ...match, epsilon: parsed } });
  };

  const matchPlaceholder =
    match.mode === "sha256"
      ? "a3f5c7d1e8b2..."
      : match.mode === "regex"
        ? "accuracy: \\d+\\.\\d+"
        : match.mode === "numeric"
          ? "0.9542"
          : match.mode === "custom"
            ? "python validate.py"
            : "PASSED";

  const inlineInput: React.CSSProperties = {
    ...lgInput(locked),
    minHeight: "auto",
    padding: "6px 10px",
    fontSize: 12,
    width: "auto",
  };

  const inlineLabel: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 700,
    color: lgColors.textMuted,
    minWidth: 44,
    textAlign: "right",
  };

  return (
    <div
      style={{
        border: "1px solid rgba(148, 163, 184, 0.32)",
        borderRadius: 9,
        padding: "10px 12px",
        background: "rgba(248, 250, 252, 0.7)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={inlineLabel}>Source</span>
        <select
          disabled={locked}
          value={source.kind}
          onChange={(e) => setSourceKind(e.target.value as OutputSource["kind"])}
          style={{ ...inlineInput, minWidth: 90 }}
        >
          <option value="stdout">stdout</option>
          <option value="stderr">stderr</option>
          <option value="file">file</option>
        </select>
        {source.kind === "file" && (
          <input
            disabled={locked}
            value={source.path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="results/output.txt"
            style={{ ...inlineInput, flex: 1, fontFamily: F.mono }}
          />
        )}
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={inlineLabel}>Match</span>
        <select
          disabled={locked}
          value={match.mode}
          onChange={(e) => setMatchMode(e.target.value as OutputMatch["mode"])}
          style={{ ...inlineInput, minWidth: 90 }}
        >
          <option value="contains">contains</option>
          <option value="regex">regex</option>
          <option value="numeric">numeric</option>
          <option value="sha256">sha256</option>
          <option value="custom">custom</option>
        </select>
        <input
          disabled={locked}
          value={match.value}
          onChange={(e) => setMatchValue(e.target.value)}
          placeholder={matchPlaceholder}
          style={{
            ...inlineInput,
            flex: 1,
            fontFamily: match.mode === "contains" ? F.sans : F.mono,
          }}
        />
        {match.mode === "numeric" && (
          <>
            <span style={{ fontSize: 12, color: lgColors.textMuted, whiteSpace: "nowrap" }}>±</span>
            <input
              disabled={locked}
              value={match.epsilon}
              onChange={(e) => setEpsilon(e.target.value)}
              placeholder="1e-6"
              style={{ ...inlineInput, width: 80, fontFamily: F.mono }}
            />
          </>
        )}
      </div>

      {!locked && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onRemove}
            style={{
              ...lgActionButton("danger"),
              width: "auto",
              padding: "3px 9px",
              fontSize: 11,
              fontWeight: 700,
              gap: 5,
            }}
          >
            {Ic.x(10)} Remove
          </button>
        </div>
      )}
    </div>
  );
}

// ================================================
// Aside cards
// ================================================

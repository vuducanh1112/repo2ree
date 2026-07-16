import type { ExperimentResourceEstimates, ReeExperiment } from "@core/ree/ReeSpec";
import type { LogEntry } from "@core/ree/ReeTypes";
import type { ExperimentRunOutputs } from "@core/runs/ExperimentRun";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import {
  experimentRunScriptPath,
  experimentVerifyScriptPath,
} from "@shell/data/scriptTemplates/paths";
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
import { useEffect, useState } from "react";
import { LogPanel } from "../../components/logPanel";
import { RunActionButton } from "../../components/RunActionButton";
import { RunScriptCard } from "../../components/RunScriptCard";
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
  scriptContent,
  verifyScriptContent,
  onUpdate,
  onSaveScript,
  onSaveVerifyScript,
  onBack,
  runState,
}: {
  experiment: ReeExperiment;
  index: number;
  otherNames: string[];
  locked: boolean;
  scriptContent: string;
  verifyScriptContent: string;
  onUpdate: (patch: Partial<ReeExperiment>) => void;
  onSaveScript: (path: string, content: string) => void;
  onSaveVerifyScript: (path: string, content: string) => void;
  onBack: () => void;
  runState: RunState | null;
}) {
  const { trimmedName, isDuplicateName, isInvalidName, canRun } = experimentValidation(
    experiment,
    otherNames,
  );
  // Backend-owned starter templates and path conventions; prefill the editors
  // until a script exists.
  const { data: templates } = useScriptTemplates();

  // The experiment owns its scripts. The backend settles the run-script path
  // when the experiment is named; until that (and for the verify script, which
  // is only declared once authored) derive the same destination from the
  // catalog's published patterns so there is somewhere to save to.
  const fallbackName = experiment.name || `experiment-${index + 1}`;
  const scriptPath =
    experiment.runScript || (templates ? experimentRunScriptPath(templates, fallbackName) : "");
  const verifyScriptPath =
    experiment.verifyScript ||
    (templates ? experimentVerifyScriptPath(templates, fallbackName) : "");

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

        <DetailField
          label="Run script"
          help="This experiment owns its run script: it fully defines how it executes, including entering the built runtime (e.g. its own docker run)."
        >
          <RunScriptCard
            scriptPath={scriptPath}
            currentContent={scriptContent}
            disabled={locked || !scriptPath}
            label="Experiment run script"
            helper="Saved to the workspace overlay and run from the workspace root."
            defaultTemplate={templates?.experiment.templates[0]?.body ?? ""}
            onSave={(content) => onSaveScript(scriptPath, content)}
          />
        </DetailField>

        <DetailField
          label="Verify script"
          help="Checks the run's results afterwards — a plain script run from the workspace root after the run script, whose exit code is the verdict (0 = the claimed result was reproduced). It reads what it checks straight from the workspace; to check stdout, have the run script write it to a file (e.g. `… | tee results/run.log`). Start from a template for the standard cases."
        >
          {!locked && (
            <VerifyTemplatePicker onInsert={(body) => onSaveVerifyScript(verifyScriptPath, body)} />
          )}
          <RunScriptCard
            scriptPath={verifyScriptPath}
            currentContent={verifyScriptContent}
            disabled={locked || !verifyScriptPath}
            label="Experiment verify script"
            helper="Runs from the workspace root after the run script; its exit code is the verdict (0 = pass). Reads outputs straight from the workspace — no injected variables."
            defaultTemplate={templates?.verify[0]?.body ?? ""}
            saveButtonContent="Save verify script"
            savedLabel="Saved verify script"
            unsavedLabel="Unsaved verify script"
            onSave={(content) => onSaveVerifyScript(verifyScriptPath, content)}
          />
        </DetailField>

        <DetailField
          label="Runtime estimate"
          help="Expected wall-clock duration for a typical successful run."
        >
          <input
            disabled={locked}
            value={experiment.runtimeEstimate}
            onChange={(e) => onUpdate({ runtimeEstimate: e.target.value })}
            placeholder="5-10 min"
            style={{ ...lgInput(locked), fontFamily: F.mono, fontSize: 13 }}
          />
        </DetailField>

        <ResourceEstimatesEditor
          estimates={experiment.resourceEstimates}
          locked={locked}
          onChange={(resourceEstimates) => onUpdate({ resourceEstimates })}
        />

        <OutputPathsEditor
          outputPaths={experiment.outputPaths}
          locked={locked}
          onChange={(outputPaths) => onUpdate({ outputPaths })}
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

// ================================================
// Verify template picker
// ================================================

// Inserting a template saves it to the verify script slot, replacing whatever
// is there — the card below then shows it for editing. The templates are
// backend-owned; until they load, the picker renders just its caption.
function VerifyTemplatePicker({ onInsert }: { onInsert: (body: string) => void }) {
  const { data: templates } = useScriptTemplates();
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
      <span
        style={{ fontSize: 11, fontWeight: 700, color: lgColors.textMuted, alignSelf: "center" }}
      >
        Templates:
      </span>
      {(templates?.verify ?? []).map((template) => (
        <button
          key={template.key}
          type="button"
          title={`${template.description} Inserting replaces the current verify script.`}
          onClick={() => onInsert(template.body)}
          style={{
            ...lgGlassButton(),
            padding: "3px 9px",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {template.label}
        </button>
      ))}
    </div>
  );
}

// The selected experiment's Run / Delete controls, rendered in the page
// header's top-right (like the Build Runtime page's run controls) rather than
// inside the detail panel.
export function ExperimentHeaderActions({
  locked,
  canRun,
  isRunning,
  onRun,
  onRemove,
}: {
  locked: boolean;
  canRun: boolean;
  isRunning: boolean;
  onRun: () => void;
  onRemove: () => void;
}) {
  const runTitle = canRun
    ? "Run the experiment and verify its result"
    : "Add a unique name and run script before running";
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

/**
 * One-line explanation of a terminal run's verdict. The verify script's exit
 * code is the whole story — a pass means the run script exited 0 and, when
 * declared, the verify script exited 0 too; anything else is a fail.
 */
function runResultSummary(outputs: ExperimentRunOutputs): string {
  const hasVerify = outputs.verifyExitCode !== undefined;
  if (outputs.verdict === "pass") {
    return hasVerify
      ? "Verify script exited 0 — the claimed result was reproduced."
      : "Command exited 0 — no verify script declared.";
  }
  if (hasVerify && outputs.exitCode === 0) {
    return `Verify script failed (exit code ${outputs.verifyExitCode ?? "?"}) — result not reproduced.`;
  }
  return `Run script failed (exit code ${outputs.exitCode ?? "?"}).`;
}

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
    <section aria-label="Run result" style={lgStyles.fieldFrame}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={lgStyles.label}>Run result</span>
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
          <div style={{ fontSize: 12, color: lgColors.textMuted }}>{runResultSummary(outputs)}</div>
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
    </section>
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
// Declared output paths editor
// ================================================

// One workspace-relative path per line. A pure declaration: it tells readers
// (and the drift check) which files the run legitimately (re)writes — the
// verify script is what actually checks them.
function parseOutputPathLines(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function OutputPathsEditor({
  outputPaths,
  locked,
  onChange,
}: {
  outputPaths: string[];
  locked: boolean;
  onChange: (outputPaths: string[]) => void;
}) {
  // Local text state so in-progress newlines/whitespace survive the
  // parse-normalize round-trip through the parent; the effect only resets the
  // text when the persisted list diverges from what the text already encodes
  // (e.g. an external update), never while typing.
  const [text, setText] = useState(outputPaths.join("\n"));
  useEffect(() => {
    setText((current) =>
      parseOutputPathLines(current).join("\n") === outputPaths.join("\n")
        ? current
        : outputPaths.join("\n"),
    );
  }, [outputPaths]);

  return (
    <div style={lgStyles.fieldFrame}>
      <span style={lgStyles.label}>Output files</span>
      <textarea
        aria-label="Output files"
        disabled={locked}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(parseOutputPathLines(e.target.value));
        }}
        placeholder={"results/output.csv\nfigures/plot.png"}
        rows={3}
        spellCheck={false}
        style={{
          ...lgInput(locked),
          resize: "vertical",
          minHeight: 66,
          lineHeight: 1.6,
          fontFamily: F.mono,
          fontSize: 12,
        }}
      />
      <span style={lgStyles.helper}>
        Workspace-relative files this experiment produces, one per line. Captured after each run;
        include them in the bundle from the Seal page. Also excluded from workspace-drift checks.
      </span>
    </div>
  );
}

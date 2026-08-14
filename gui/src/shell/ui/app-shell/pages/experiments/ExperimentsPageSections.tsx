import { PAGE } from "@core/app-shell/pages";
import { experimentValidation, expId } from "@core/ree/experimentRules";
import type { ExperimentResourceEstimates, ReeExperiment } from "@core/ree/ReeSpec";
import type { LogEntry } from "@core/ree/ReeTypes";
import type { ExperimentRunOutputs } from "@core/runs/ExperimentRun";
import type { ReeRunFailure } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { runFailurePresentation } from "@core/runs/runFailurePresentation";
import { useGenerateExperimentScript } from "@shell/data/scriptInference/mutations";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import {
  experimentRunScriptPath,
  experimentVerifyScriptPath,
} from "@shell/data/scriptTemplates/paths";
import { GlassPanel } from "@shell/ui/app-shell/components/GlassPageShell";
import { GlassPanelFooter } from "@shell/ui/app-shell/components/GlassPanelFooter";
import { Button } from "@shell/ui/shared/components/Button";
import { Field, Input, Textarea } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { failureTone, stageTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import type React from "react";
import { useEffect, useState } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GenerateScriptControl } from "../../components/GenerateScriptControl";
import { RunActionButton } from "../../components/RunActionButton";
import { RunScriptCard } from "../../components/RunScriptCard";
import styles from "./ExperimentsPage.module.css";
import type { RunState } from "./useExperimentRun";

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

  // Read-only inference: generate an experiment run scaffold from the built
  // runtime and load it into the editor (never written here). Requires the
  // experiment to be declared (named + saved) so the backend can resolve it.
  const generateExperiment = useGenerateExperimentScript(experiment.name);
  const [runScriptExternalEdit, setRunScriptExternalEdit] = useState<
    { content: string; nonce: number } | undefined
  >();

  return (
    <GlassPanel clipped>
      <DetailBreadcrumb index={index} onBack={onBack} />

      <div className={styles.detailBody}>
        <DetailField label="Name" required>
          <Input
            disabled={locked}
            value={experiment.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="smoke-test"
            aria-invalid={isDuplicateName || isInvalidName}
          />
          {isDuplicateName && (
            <span className={styles.fieldError}>Another experiment already uses this name.</span>
          )}
          {!isDuplicateName && isInvalidName && (
            <span className={styles.fieldError}>
              Use only letters, digits, spaces, '.', '_' and '-'.
            </span>
          )}
        </DetailField>

        <DetailField label="Description" help="What this experiment verifies in the REE.">
          <Textarea
            disabled={locked}
            value={experiment.description}
            onChange={(e) => onUpdate({ description: e.target.value })}
            placeholder="Imports the main package and runs the smoke suite."
            rows={3}
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
            templates={templates?.experiment.templates}
            externalEdit={runScriptExternalEdit}
            generateSlot={
              <GenerateScriptControl
                generate={generateExperiment}
                noun="experiment run script"
                disabled={locked || !scriptPath || !experiment.name}
                onLoad={(body) =>
                  setRunScriptExternalEdit((prev) => ({
                    content: body,
                    nonce: (prev?.nonce ?? 0) + 1,
                  }))
                }
              />
            }
            onSave={(content) => onSaveScript(scriptPath, content)}
          />
        </DetailField>

        <DetailField
          label="Verify script"
          help="Validates the run's results afterwards — a plain script run from the workspace root after the run script, whose exit code is the verdict (0 = the declared validation passed). It reads what it checks straight from the workspace; to check stdout, have the run script write it to a file (e.g. `… | tee results/run.log`). Start from a template for the standard cases."
        >
          <RunScriptCard
            scriptPath={verifyScriptPath}
            currentContent={verifyScriptContent}
            disabled={locked || !verifyScriptPath}
            label="Experiment verify script"
            helper="Runs from the workspace root after the run script; its exit code is the verdict (0 = pass). Reads outputs straight from the workspace — no injected variables."
            templates={templates?.verify}
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
          <Input
            disabled={locked}
            value={experiment.runtimeEstimate}
            onChange={(e) => onUpdate({ runtimeEstimate: e.target.value })}
            placeholder="5-10 min"
            flavor="code"
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

      <GlassPanelFooter
        action={
          <Button
            variant="primary"
            icon={Ic.check(15)}
            onClick={onBack}
            disabled={!locked && !canRun}
          >
            Save &amp; back to catalog
          </Button>
        }
      >
        {!locked && trimmedName === ""
          ? "A name is required."
          : !locked && isDuplicateName
            ? "Fix the duplicate name to continue."
            : !locked && isInvalidName
              ? "Fix the invalid name to continue."
              : "Edits save automatically."}
      </GlassPanelFooter>
    </GlassPanel>
  );
}

function DetailBreadcrumb({ index, onBack }: { index: number; onBack: () => void }) {
  return (
    <div className={styles.breadcrumb}>
      <Button size="small" icon={Ic.arrowLeft(13)} onClick={onBack}>
        Experiments
      </Button>
      <span aria-hidden className={styles.breadcrumbSep}>
        /
      </span>
      <span className={styles.expId}>{expId(index)}</span>
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
  onCancel,
  onRemove,
}: {
  locked: boolean;
  canRun: boolean;
  isRunning: boolean;
  onRun: () => void;
  onCancel: () => void;
  onRemove: () => void;
}) {
  const runTitle = canRun
    ? "Run the experiment and verify its result"
    : "Add a unique name and run script before running";
  return (
    <div className={styles.detailActions}>
      <RunActionButton
        label={isRunning ? "Running…" : "Run"}
        running={isRunning}
        disabled={!canRun || isRunning}
        iconSize={12}
        title={runTitle}
        variant="secondary"
        size="small"
        tint={stageTone(PAGE.EXPERIMENTS)}
        onRun={onRun}
        onCancel={onCancel}
      />
      {!locked && (
        <Button variant="danger" size="small" icon={Ic.x(12)} onClick={onRemove}>
          Delete
        </Button>
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
    <div className={styles.field}>
      <span className={styles.fieldLabel}>
        {label}
        {required && <span className={styles.required}>*</span>}
      </span>
      {children}
      {help && <span className={styles.fieldHelp}>{help}</span>}
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
      ? "Verify script exited 0 — the declared validation passed."
      : "Command exited 0 — no verify script declared.";
  }
  if (hasVerify && outputs.exitCode === 0) {
    return `Verify script failed (exit code ${outputs.verifyExitCode ?? "?"}) — declared validation failed.`;
  }
  return `Run script failed (exit code ${outputs.exitCode ?? "?"}).`;
}

/**
 * The typed reason a run failed without producing outputs — a transport or
 * workbench-availability failure the plain "no output data" line used to
 * swallow. Reuses the shared {@link runFailurePresentation} policy so this reads
 * the same as the run HUD's failure note.
 */
function ExperimentFailureNote({ failure }: { failure: ReeRunFailure }) {
  const view = runFailurePresentation(failure);
  const color = failureTone(view.tone);
  return (
    <div className={styles.failure} style={cssVars({ "--failure-ink": color })}>
      <div className={styles.failureHead}>
        <span className={styles.failureLabel}>{view.label}</span>
        {view.retryable && (
          <span className={styles.failureRetryable} title="Safe to retry">
            retryable
          </span>
        )}
      </div>
      <div className={styles.failureMessage}>{view.message}</div>
    </div>
  );
}

function RunResultPanel({ runState }: { runState: RunState }) {
  const isTerminal = isTerminalReeRunStatus(runState.status);
  const { outputs } = runState;
  const logEntry: LogEntry | null =
    runState.logLines.length > 0 ? { lines: runState.logLines, ts: runState.startedAt } : null;

  const headerColor =
    outputs?.verdict === "pass"
      ? "var(--verdict-pass-ink)"
      : outputs?.verdict === "fail" || runState.status === "failed"
        ? "var(--verdict-fail-ink)"
        : "var(--verdict-idle-ink)";

  const headerBg =
    outputs?.verdict === "pass"
      ? "var(--verdict-pass-wash)"
      : outputs?.verdict === "fail" || runState.status === "failed"
        ? "var(--verdict-fail-wash)"
        : "var(--verdict-idle-wash)";

  return (
    <section aria-label="Run result" className={styles.field}>
      <div className={styles.resultHead}>
        <span className={styles.fieldLabel}>Run result</span>
        <span
          className={styles.verdict}
          style={cssVars({ "--verdict-ink": headerColor, "--verdict-wash": headerBg })}
        >
          {!isTerminal ? runState.status : (outputs?.verdict ?? runState.status)}
        </span>
      </div>

      {!isTerminal && <div className={styles.running}>{Ic.loader(13)} Running experiment…</div>}

      {isTerminal && outputs && (
        <div className={styles.resultDetail}>
          <div className={styles.resultSummary}>{runResultSummary(outputs)}</div>
        </div>
      )}

      {isTerminal && !outputs && runState.failure && (
        <ExperimentFailureNote failure={runState.failure} />
      )}

      {isTerminal && !outputs && !runState.failure && (
        <div className={styles.resultMissing}>
          Run {runState.status} — no output data available.
        </div>
      )}

      <div className={styles.resultLog}>
        <CollapsibleLogCard log={logEntry} running={!isTerminal} title="Run log" maxHeight={320} />
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
    <div className={styles.field}>
      <span className={styles.fieldLabel}>Resource estimates</span>
      <div className={styles.estimateGrid}>
        {resourceFields.map(({ field, label, placeholder }) => (
          <Field key={field} label={label}>
            {(bound) => (
              <Input
                {...bound}
                disabled={locked}
                value={estimates[field]}
                onChange={(e) => updateField(field, e.target.value)}
                placeholder={placeholder}
                flavor="code"
                density="compact"
              />
            )}
          </Field>
        ))}
      </div>
      <span className={styles.fieldHelp}>
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
    <div className={styles.field}>
      <span className={styles.fieldLabel}>Output files</span>
      <Textarea
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
        flavor="code"
      />
      <span className={styles.fieldHelp}>
        Workspace-relative files this experiment produces, one per line. Captured after each run;
        include them in the bundle from the Seal page. Also excluded from workspace-drift checks.
      </span>
    </div>
  );
}

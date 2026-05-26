import type React from "react";
import { useState } from "react";
import type {
  ExpectedOutput,
  OutputMatch,
  OutputSource,
  ReeExperiment,
} from "../../../../../core/ree/ReeSpec";
import { Ic } from "../../../shared/components/Icon";
import {
  lgActionButton,
  lgColors,
  lgContentCard,
  lgGlassButton,
  lgInput,
  lgNextButton,
  lgStyles,
  lgSuggestionButton,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { expId } from "./experimentsPageHelpers";

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

// ================================================
// Catalog (cards)
// ================================================

export function ExperimentCardList({
  experiments,
  locked,
  onSelect,
  onAdd,
  onRemove,
}: {
  experiments: ReeExperiment[];
  locked: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  if (experiments.length === 0) {
    return <ExperimentEmptyState locked={locked} onAdd={onAdd} />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {experiments.map((exp, index) => (
        <ExperimentCard
          key={`exp-${String(index)}`}
          experiment={exp}
          index={index}
          locked={locked}
          onSelect={() => onSelect(index)}
          onRemove={() => onRemove(index)}
        />
      ))}
    </div>
  );
}

function ExperimentCard({
  experiment,
  index,
  locked,
  onSelect,
  onRemove,
}: {
  experiment: ReeExperiment;
  index: number;
  locked: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const name = experiment.name.trim();
  const command = experiment.command.trim();
  const description = experiment.description.trim();
  const outputCount = experiment.outputs?.length ?? 0;

  return (
    <div
      style={{
        border: hovered
          ? "1px solid rgba(14, 165, 233, 0.55)"
          : "1px solid rgba(125, 211, 252, 0.42)",
        borderRadius: 11,
        background: "rgba(255, 255, 255, 0.7)",
        boxShadow: hovered
          ? "0 14px 30px rgba(14, 165, 233, 0.16)"
          : "0 6px 16px rgba(15, 23, 42, 0.05)",
        transition: "border-color 0.15s, box-shadow 0.15s",
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={onSelect}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
        style={{
          width: "100%",
          textAlign: "left",
          background: "transparent",
          border: "none",
          padding: "14px 16px 12px",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: "0.08em",
              color: lgColors.cyan,
              border: "1px solid rgba(14, 165, 233, 0.32)",
              background: "rgba(240, 249, 255, 0.85)",
              borderRadius: 6,
              padding: "2px 7px",
            }}
          >
            {expId(index)}
          </span>
          <h3
            style={{
              margin: 0,
              fontSize: 15,
              fontWeight: 700,
              color: name ? lgColors.text : lgColors.textMuted,
              fontStyle: name ? "normal" : "italic",
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {name || "untitled experiment"}
          </h3>
          {outputCount > 0 && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: lgColors.success,
                background: "rgba(220, 252, 231, 0.85)",
                border: "1px solid rgba(34, 197, 94, 0.35)",
                borderRadius: 99,
                padding: "2px 7px",
              }}
            >
              {outputCount} {outputCount === 1 ? "output" : "outputs"}
            </span>
          )}
          <span
            style={{
              color: hovered ? lgColors.blue : lgColors.textMuted,
              display: "flex",
              transition: "color 0.15s",
            }}
          >
            {Ic.chevR(15)}
          </span>
        </div>

        <div
          style={{
            fontFamily: F.mono,
            fontSize: 12,
            color: command ? lgColors.textMid : lgColors.textMuted,
            background: "rgba(248, 250, 252, 0.78)",
            border: "1px solid rgba(148, 163, 184, 0.28)",
            borderRadius: 7,
            padding: "7px 10px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            opacity: command ? 1 : 0.7,
          }}
        >
          {command || "no command set"}
        </div>

        {description && (
          <div
            style={{
              fontSize: 12,
              color: lgColors.textMid,
              lineHeight: 1.45,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {description}
          </div>
        )}
      </button>

      {!locked && (
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            padding: "0 12px 10px",
          }}
        >
          <button
            type="button"
            onClick={onRemove}
            style={{
              ...lgActionButton("danger"),
              width: "auto",
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 700,
              gap: 5,
            }}
          >
            {Ic.x(11)} Delete
          </button>
        </div>
      )}
    </div>
  );
}

function ExperimentEmptyState({ locked, onAdd }: { locked: boolean; onAdd: () => void }) {
  return (
    <div
      style={{
        ...lgContentCard(0),
        padding: "40px 24px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        textAlign: "center",
      }}
    >
      <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.terminal(28)}</span>
      <div style={{ fontSize: 14, fontWeight: 700, color: lgColors.text }}>No experiments yet</div>
      <div
        style={{
          fontSize: 12,
          color: lgColors.textMid,
          maxWidth: 320,
          lineHeight: 1.5,
        }}
      >
        Add a verification command and the assembled REE will be checked against it.
      </div>
      {!locked && (
        <button
          type="button"
          onClick={onAdd}
          style={{
            ...lgGlassButton(),
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 4,
          }}
        >
          {Ic.plus(13)} Add experiment
        </button>
      )}
    </div>
  );
}

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
  onRemove,
}: {
  experiment: ReeExperiment;
  index: number;
  otherNames: string[];
  locked: boolean;
  onUpdate: (patch: Partial<ReeExperiment>) => void;
  onBack: () => void;
  onRemove: () => void;
}) {
  const trimmedName = experiment.name.trim();
  const isDuplicateName = trimmedName !== "" && otherNames.includes(trimmedName);
  const canRun = trimmedName !== "" && !isDuplicateName;

  return (
    <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
      <DetailBreadcrumb
        index={index}
        locked={locked}
        canRun={canRun}
        onBack={onBack}
        onRemove={onRemove}
      />

      <div style={{ ...lgStyles.sectionBody, display: "flex", flexDirection: "column", gap: 18 }}>
        <DetailField label="Name" required>
          <input
            disabled={locked}
            value={experiment.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="smoke-test"
            style={{
              ...lgInput(locked),
              ...(isDuplicateName ? { borderColor: "rgba(239, 68, 68, 0.7)" } : {}),
            }}
          />
          {isDuplicateName && (
            <span style={{ fontSize: 11, color: lgColors.required, marginTop: 2 }}>
              Another experiment already uses this name.
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

        <OutputsEditor
          outputs={experiment.outputs}
          locked={locked}
          onChange={(outputs) => onUpdate({ outputs })}
        />
      </div>

      <div style={lgStyles.footer}>
        <span style={{ color: lgColors.textMuted, fontSize: 12 }}>
          {!locked && trimmedName === ""
            ? "A name is required."
            : !locked && isDuplicateName
              ? "Fix the duplicate name to continue."
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

function DetailBreadcrumb({
  index,
  locked,
  canRun,
  onBack,
  onRemove,
}: {
  index: number;
  locked: boolean;
  canRun: boolean;
  onBack: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 18px",
        borderBottom: "1px solid rgba(125, 211, 252, 0.4)",
        background: "rgba(255, 255, 255, 0.55)",
        flexWrap: "wrap",
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
      <span style={{ flex: 1 }} />
      <button
        type="button"
        disabled
        title={canRun ? "Run is not yet wired up" : "Add a unique name before running"}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          border: "1px solid rgba(148, 163, 184, 0.34)",
          background: "rgba(241, 245, 249, 0.72)",
          color: lgColors.textMuted,
          padding: "6px 14px",
          borderRadius: 8,
          fontWeight: 700,
          fontSize: 12,
          cursor: "not-allowed",
          opacity: canRun ? 1 : 0.45,
        }}
      >
        {Ic.play(12)} Run
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

export function ExperimentsCoverageAside({
  total,
  withName,
  withCommand,
  withDescription,
  withOutputs,
}: {
  total: number;
  withName: number;
  withCommand: number;
  withDescription: number;
  withOutputs: number;
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
              {incomplete} need name & command.
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
        They are optional, but they raise the achievable reproducibility level.
      </div>
    </section>
  );
}

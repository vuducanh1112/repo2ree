import { useCallback } from "react";
import {
  createEmptyReeActivation,
  createEmptyRuntimeEntry,
  type ReeActivation,
  type RuntimeEntry,
  type RuntimeEntryKind,
} from "../../../../../core/ree/ReeSpec";
import {
  activationFooterHint,
  activationRunLabel,
  canRunActivation,
} from "../../../../../core/ree-assembly/activationUiState";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import { resolvedRuntimePath } from "../../../../../core/ree-assembly/buildRuntimeUiState";
import { resolvedSbomPath } from "../../../../../core/ree-assembly/sbomUiState";
import { workspaceFileExists } from "../../../../../core/workspace/fileTreeTraversal";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgOutcomeBadge,
  lgPillChip,
  lgPrimaryActionButton,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { C, F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassCancelButton } from "../../components/GlassCancelButton";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { ActivationTargetCard } from "./sections";

const ACTIVATION_PAGE_COLOR = "#7c3aed";

const ENTRY_KINDS: { kind: RuntimeEntryKind; label: string; desc: string; soon?: boolean }[] = [
  { kind: "docker", label: "Docker", desc: "Spin up the runtime container image" },
  {
    kind: "native",
    label: "Native / venv",
    desc: "Run directly on the workbench (with optional activate script)",
  },
  {
    kind: "singularity",
    label: "Singularity",
    desc: "Singularity/Apptainer container",
    soon: true,
  },
  { kind: "vm", label: "VM", desc: "Virtual machine substrate", soon: true },
];

function SubstratePicker({
  entry,
  onChange,
}: {
  entry: RuntimeEntry;
  onChange: (next: RuntimeEntry) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {ENTRY_KINDS.map(({ kind, label, desc, soon }) => {
        const active = entry.kind === kind;
        return (
          <button
            key={kind}
            type="button"
            disabled={!!soon}
            onClick={() => {
              if (soon) return;
              if (kind === "native")
                onChange({
                  kind: "native",
                  activate: entry.kind === "native" ? entry.activate : "",
                });
              else if (kind === "docker") onChange({ kind: "docker" });
              else if (kind === "singularity") onChange({ kind: "singularity", sif: "" });
              else onChange({ kind: "vm", host: "" });
            }}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "10px 12px",
              borderRadius: 8,
              border: `1.5px solid ${active ? ACTIVATION_PAGE_COLOR : C.border}`,
              background: active ? `${ACTIVATION_PAGE_COLOR}10` : C.surface,
              cursor: soon ? "not-allowed" : "pointer",
              opacity: soon ? 0.5 : 1,
              textAlign: "left",
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                border: `2px solid ${active ? ACTIVATION_PAGE_COLOR : C.border}`,
                background: active ? ACTIVATION_PAGE_COLOR : "transparent",
                marginTop: 2,
                flexShrink: 0,
              }}
            />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.text, fontFamily: F.sans }}>
                {label}
                {soon && (
                  <span style={{ marginLeft: 6, fontSize: 10, color: C.textMid, fontWeight: 400 }}>
                    coming soon
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: C.textMid, fontFamily: F.sans, marginTop: 2 }}>
                {desc}
              </div>
            </div>
          </button>
        );
      })}

      {entry.kind === "native" && (
        <div style={{ marginTop: 4 }}>
          <label
            htmlFor="native-activate"
            style={{ fontSize: 11, fontWeight: 600, color: C.textMid, fontFamily: F.sans }}
          >
            Activate script (optional)
          </label>
          <input
            id="native-activate"
            type="text"
            value={entry.activate}
            placeholder="e.g. source .venv/bin/activate"
            onChange={(e) => onChange({ kind: "native", activate: e.target.value })}
            style={{
              display: "block",
              marginTop: 4,
              width: "100%",
              padding: "6px 10px",
              fontSize: 12,
              fontFamily: F.mono,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              background: C.surface,
              color: C.text,
              boxSizing: "border-box",
            }}
          />
        </div>
      )}
    </div>
  );
}

function ActivationRunControls({
  running,
  runDone,
  disabled,
  onRun,
  onCancel,
}: {
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  onRun: () => void;
  onCancel?: () => void;
}) {
  const label = activationRunLabel({ running, runDone });
  return (
    <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
      <button
        type="button"
        onClick={onRun}
        disabled={disabled}
        style={lgPrimaryActionButton(disabled)}
      >
        <span
          style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
        >
          {running ? Ic.loader(14) : Ic.play(14)}
        </span>
        {label}
      </button>
      {running && onCancel && <GlassCancelButton onClick={onCancel} />}
    </div>
  );
}

export function PageTestActivation({
  assemblyStep,
  ree,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGoFields,
  missing,
  params,
  onReeSpecChange,
}: AssemblyPageProps) {
  const files = workspaceFiles || [];

  const activation: ReeActivation = ree.activation ?? createEmptyReeActivation();
  const runtimeEntry: RuntimeEntry = ree.runtime_entry ?? createEmptyRuntimeEntry();

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomPathExists = sbomPath ? workspaceFileExists(files, sbomPath) : false;

  const activationParams: ReeAssemblyRunParams<"activation"> =
    params as ReeAssemblyRunParams<"activation">;

  const canRun = canRunActivation({
    running,
    hasMissing: missing.length > 0,
    runtimePathExists,
  });
  const activationReady = runDone && canRun;

  const handleCommandChange = useCallback(
    (command: string) => {
      onReeSpecChange?.((current) => ({
        ...current,
        activation: { ...current.activation, command },
      }));
    },
    [onReeSpecChange],
  );

  const handleEntryChange = useCallback(
    (entry: RuntimeEntry) => {
      onReeSpecChange?.((current) => ({ ...current, runtime_entry: entry }));
    },
    [onReeSpecChange],
  );

  const commandLabel = activation.command?.trim()
    ? activation.command.length > 40
      ? `${activation.command.slice(0, 40)}…`
      : activation.command
    : null;

  return (
    <div style={pageRoot}>
      <GlassPageHeader
        icon={Ic.shield(24)}
        iconTint={{
          color: ACTIVATION_PAGE_COLOR,
          border: `${ACTIVATION_PAGE_COLOR}55`,
          shadow: `${ACTIVATION_PAGE_COLOR}28`,
        }}
        title="Test Activation"
        subtitle="Verify the packaged runtime actually starts and activates."
        badges={
          <>
            {commandLabel && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{commandLabel}</span>
            )}
            <span style={lgStatusBadge(activationReady)}>
              {activationReady ? "Activation ready" : "Activation pending"}
            </span>
            {runDone && badge && (
              <span style={lgOutcomeBadge(badge.color, badge.bg)}>
                {Ic.check(11)} {badge.label}
              </span>
            )}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last verified" ts={ts} />}
            <ActivationRunControls
              running={running}
              runDone={runDone}
              disabled={!canRun}
              onRun={() => onRun(assemblyStep.key, activationParams)}
              onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            />
          </div>
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.shield(19)}
              color={ACTIVATION_PAGE_COLOR}
              title="Activation Command"
              subtitle="The command run inside the runtime to verify it starts. Leave empty to use the built-in liveness probe."
            />

            <textarea
              value={activation.command}
              onChange={(e) => handleCommandChange(e.target.value)}
              placeholder="e.g. python -c 'import numpy; print(ok)'"
              rows={3}
              style={{
                width: "100%",
                padding: "10px 12px",
                fontSize: 12,
                fontFamily: F.mono,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                background: C.surface,
                color: C.text,
                resize: "vertical",
                marginTop: 10,
                boxSizing: "border-box",
              }}
            />

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.cpu(19)}
                color={ACTIVATION_PAGE_COLOR}
                title="Runtime Substrate"
                subtitle="How the workbench enters the runtime. Shared by activation and all experiments."
              />
              <div style={{ marginTop: 10 }}>
                <SubstratePicker entry={runtimeEntry} onChange={handleEntryChange} />
              </div>
            </div>

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.cpu(19)}
                color={ACTIVATION_PAGE_COLOR}
                title="Runtime Under Test"
                subtitle="Activation reuses the runtime artifact from Build Runtime and the inventory context from Generate SBOM."
              />

              <ActivationTargetCard
                runtimePath={runtimePath}
                runtimePathExists={runtimePathExists}
                sbomPath={sbomPath}
                sbomPathExists={sbomPathExists}
              />
            </div>

            <div style={{ marginTop: 22 }}>
              <CollapsibleLogCard
                log={log}
                running={running}
                title={ts ? "Activation log" : "Activation logs"}
              />
            </div>
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
              {activationFooterHint({ runDone })}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}

const pageRoot: React.CSSProperties = {
  height: "100%",
  minHeight: 0,
  overflow: "auto",
  padding: "46px 36px 32px",
  color: lgColors.text,
};

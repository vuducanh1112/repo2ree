import { createEmptyReeActivation, type ReeActivation } from "@core/ree/ReeSpec";
import {
  activationFooterHint,
  activationRunLabel,
  canRunActivation,
} from "@core/ree-assembly/activationUiState";
import type { ReeAssemblyRunParams } from "@core/ree-assembly/assemblyTypes";
import { resolvedRuntimePath } from "@core/ree-assembly/buildRuntimeUiState";
import { resolvedSbomPath } from "@core/ree-assembly/sbomUiState";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgOutcomeBadge,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { C, F } from "@shell/ui/theme/theme";
import { useCallback } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { RunActionButton } from "../../components/RunActionButton";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { ActivationTargetCard } from "./sections";

const ACTIVATION_PAGE_COLOR = "#7c3aed";

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
  return (
    <RunActionButton
      label={activationRunLabel({ running, runDone })}
      running={running}
      disabled={disabled}
      onRun={onRun}
      onCancel={onCancel}
    />
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

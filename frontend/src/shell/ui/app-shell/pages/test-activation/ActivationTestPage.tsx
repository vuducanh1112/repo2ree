import { useCallback, useMemo, useState } from "react";
import {
  type ActivationScriptSource,
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
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassCancelButton } from "../../components/GlassCancelButton";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { ActivationScriptCard, ActivationTargetCard } from "./sections";

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
  onPersistWorkspaceFile,
}: AssemblyPageProps) {
  const files = workspaceFiles || [];

  const scriptPath = ree.activation_script || "";
  const scriptFile = useMemo(
    () => (scriptPath ? findFileByPath(files, scriptPath) : null),
    [files, scriptPath],
  );
  const scriptPresent = !!scriptFile;

  const [scriptSource, setScriptSource] = useState<ActivationScriptSource | null>(
    scriptPath ? { kind: "picked" } : null,
  );

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomPathExists = sbomPath ? workspaceFileExists(files, sbomPath) : false;

  const activationParams: ReeAssemblyRunParams<"activation"> =
    params as ReeAssemblyRunParams<"activation">;

  const scriptFileMissing = !!scriptPath && !scriptPresent;
  const canRun = canRunActivation({
    running,
    hasMissing: missing.length > 0,
    runtimePathExists,
    scriptFileMissing,
  });
  const activationReady = runDone && canRun;

  const handleCommitScript = useCallback(
    (path: string, content: string) => {
      const previousPath = scriptPath || undefined;
      onReeSpecChange?.((current) => ({ ...current, activation_script: path }));
      void onPersistWorkspaceFile?.(previousPath, path, content);
    },
    [onPersistWorkspaceFile, onReeSpecChange, scriptPath],
  );

  const handleClearScript = useCallback(
    () => onReeSpecChange?.((current) => ({ ...current, activation_script: "" })),
    [onReeSpecChange],
  );

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
            {scriptPath && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>
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
              title="Activation Script"
              subtitle="Select an existing smoke test or write the script that proves the runtime starts."
            />

            <ActivationScriptCard
              scriptPath={scriptPath}
              scriptContent={scriptFile?.content || ""}
              source={scriptSource}
              runtimeHint={runtimePath}
              files={files}
              onCommit={handleCommitScript}
              onClear={handleClearScript}
              onSourceChange={setScriptSource}
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

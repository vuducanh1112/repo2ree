import { useCallback, useMemo, useState } from "react";
import {
  type ActivationScriptSource,
  activationFooterHint,
} from "../../../../../core/ree-assembly/activationUiState";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import { resolvedRuntimePath } from "../../../../../core/ree-assembly/buildRuntimeUiState";
import { resolvedSbomPath } from "../../../../../core/ree-assembly/sbomUiState";
import { workspaceFileExists } from "../../../../../core/workspace/fileTreeTraversal";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgNextButton,
  lgOutcomeBadge,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { PAGE } from "../../state/pages";
import {
  RUNTIME_ENV_COLOR,
  RuntimeEnvironmentShell,
} from "../runtime-environment/RuntimeEnvironmentShell";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import {
  ActivationReadinessAside,
  ActivationRunConsole,
  ActivationScriptCard,
  ActivationSummaryAside,
  ActivationTargetCard,
} from "./sections";

export function PageTestActivation({
  assemblyStep,
  ree,
  badges,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGo,
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
  const buildReady = !!runtimePath && runtimePathExists;
  const activationReady = !!badges?.activation;

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

  const headerBadges = (
    <>
      {runtimePath && (
        <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{runtimePath}</span>
      )}
      {scriptPath && <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>}
      <span style={lgStatusBadge(buildReady)}>{buildReady ? "Build ready" : "Build pending"}</span>
      <span style={lgStatusBadge(!!sbomPath && sbomPathExists)}>
        {sbomPath && sbomPathExists ? "SBOM ready" : "SBOM pending"}
      </span>
      <span style={lgStatusBadge(activationReady)}>
        {activationReady ? "Activation ready" : "Activation pending"}
      </span>
      {runDone && badge && (
        <span style={lgOutcomeBadge(badge.color, badge.bg)}>
          {Ic.check(11)} {badge.label}
        </span>
      )}
    </>
  );

  const headerRight = runDone && ts ? <LastRunStamp label="Last verified" ts={ts} /> : null;

  return (
    <RuntimeEnvironmentShell
      active={PAGE.ACTIVATION}
      buildReady={buildReady}
      sbomReady={!!sbomPath && sbomPathExists}
      activationReady={activationReady}
      onGo={onGo}
      headerBadges={headerBadges}
      headerRight={headerRight}
      main={
        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.shield(19)}
              color={RUNTIME_ENV_COLOR}
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
                color={RUNTIME_ENV_COLOR}
                title="Runtime Under Test"
                subtitle="Activation reuses the runtime artifact from Build Runtime and the inventory context from Generate SBOM."
              />

              <ActivationTargetCard
                runtimePath={runtimePath}
                runtimePathExists={runtimePathExists}
                sbomPath={sbomPath}
                sbomPathExists={sbomPathExists}
                onGoBuild={() => onGo?.(PAGE.BUILD)}
                onGoSbom={() => onGo?.(PAGE.SBOM)}
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
            <button type="button" onClick={() => onGo?.(PAGE.EXPERIMENTS)} style={lgNextButton()}>
              Next: Experiments {Ic.chevR(15)}
            </button>
          </div>
        </section>
      }
      aside={
        <>
          <ActivationRunConsole
            color={RUNTIME_ENV_COLOR}
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            scriptPath={scriptPath}
            scriptPresent={scriptPresent}
            running={running}
            runDone={runDone}
            missing={missing}
            onRun={() => onRun(assemblyStep.key, activationParams)}
            onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            onGoFields={onGoFields}
          />
          <ActivationSummaryAside
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            sbomPath={sbomPath}
            sbomPathExists={sbomPathExists}
            scriptPath={scriptPath}
            scriptPresent={scriptPresent}
            runDone={runDone}
          />
          <ActivationReadinessAside
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            scriptPath={scriptPath}
            scriptPresent={scriptPresent}
            runDone={runDone}
          />
        </>
      }
    />
  );
}

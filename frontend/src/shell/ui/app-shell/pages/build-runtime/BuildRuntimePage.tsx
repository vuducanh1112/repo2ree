import { useCallback, useMemo, useState } from "react";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import type { BuildScriptSource } from "../../../../../core/ree-assembly/buildRuntimeUiState";
import {
  buildFooterHint,
  buildRunStatusLabel,
  deriveRuntimeFileSize,
  resolvedRuntimePath,
} from "../../../../../core/ree-assembly/buildRuntimeUiState";
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
  BuildLogCard,
  BuildReadinessAside,
  BuildRunConsole,
  BuildScriptCard,
  BuildSummaryAside,
  RuntimeArtifactCard,
} from "./sections";

export function PageBuildRuntime({
  assemblyStep,
  ree,
  inclusionState,
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
  onArtifactStatusChange,
  onPersistWorkspaceFile,
}: AssemblyPageProps) {
  const files = workspaceFiles || [];

  const scriptPath = ree.build_runtime_script || "";
  const scriptFile = useMemo(
    () => (scriptPath ? findFileByPath(files, scriptPath) : null),
    [files, scriptPath],
  );
  const scriptContent = scriptFile?.content || "";

  const [scriptSource, setScriptSource] = useState<BuildScriptSource | null>(
    scriptPath ? { kind: "picked" } : null,
  );

  const buildParams: ReeAssemblyRunParams<"build"> = {
    ...(params as ReeAssemblyRunParams<"build">),
    build_runtime_script_path: scriptPath,
  };

  const handleRuntimeChange = useCallback(
    (path: string) => onReeSpecChange?.((current) => ({ ...current, runtime: path })),
    [onReeSpecChange],
  );

  const handleCommitScript = useCallback(
    (path: string, content: string) => {
      const previousPath = scriptPath || undefined;
      onReeSpecChange?.((current) => ({ ...current, build_runtime_script: path }));
      void onPersistWorkspaceFile?.(previousPath, path, content);
    },
    [onPersistWorkspaceFile, onReeSpecChange, scriptPath],
  );

  const handleClearScript = useCallback(() => {
    onReeSpecChange?.((current) => ({ ...current, build_runtime_script: "" }));
  }, [onReeSpecChange]);

  const finalRuntime = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = finalRuntime ? workspaceFileExists(files, finalRuntime) : false;
  const includeRuntime = inclusionState.runtime === "included";
  const finalRuntimeFile = useMemo(
    () => (finalRuntime ? findFileByPath(files, finalRuntime) : null),
    [files, finalRuntime],
  );
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = useMemo(
    () => (sbomPath ? findFileByPath(files, sbomPath) : null),
    [files, sbomPath],
  );

  const hasScript = !!scriptPath;
  const statusLabel = buildRunStatusLabel({ running, runDone, hasScript });
  const sbomReady = !!sbomPath && !!sbomNode;
  const activationReady = !!badges?.activation;

  const headerBadges = (
    <>
      {scriptPath && <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>}
      <span style={lgStatusBadge(runDone)}>{statusLabel}</span>
      <span style={lgStatusBadge(sbomReady)}>{sbomReady ? "SBOM ready" : "SBOM pending"}</span>
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

  const headerRight = runDone && ts ? <LastRunStamp label="Last built" ts={ts} /> : null;

  return (
    <RuntimeEnvironmentShell
      active={PAGE.BUILD}
      buildReady={!!finalRuntime && runtimePathExists}
      sbomReady={sbomReady}
      activationReady={activationReady}
      onGo={onGo}
      headerBadges={headerBadges}
      headerRight={headerRight}
      main={
        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.terminal(19)}
              color={RUNTIME_ENV_COLOR}
              title="Build Script"
              subtitle="One script — pick existing, write your own, or generate from a base."
            />

            <BuildScriptCard
              scriptPath={scriptPath}
              scriptContent={scriptContent}
              source={scriptSource}
              runtimeHint={finalRuntime}
              files={files}
              onCommit={handleCommitScript}
              onClear={handleClearScript}
              onSourceChange={setScriptSource}
            />

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.archive(19)}
                color={RUNTIME_ENV_COLOR}
                title="Runtime Artifact"
                subtitle="The file produced by your build, consumed by SBOM and activation."
              />

              <RuntimeArtifactCard
                runtimePath={finalRuntime}
                runtimeSize={finalRuntimeSize}
                runtimePathExists={runtimePathExists}
                includeRuntime={includeRuntime}
                files={files}
                onRuntimeChange={handleRuntimeChange}
                onIncludedToggle={() =>
                  onArtifactStatusChange?.((current) => ({
                    ...current,
                    runtimeIncluded: !includeRuntime,
                  }))
                }
              />
            </div>

            <BuildLogCard log={log} running={running} ts={ts} />
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
              {buildFooterHint({ runDone, hasScript })}
            </span>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button type="button" onClick={() => onGo?.(PAGE.SBOM)} style={lgNextButton()}>
                Next: Generate SBOM {Ic.chevR(15)}
              </button>
            </div>
          </div>
        </section>
      }
      aside={
        <>
          <BuildRunConsole
            color={RUNTIME_ENV_COLOR}
            running={running}
            runDone={runDone}
            missing={missing}
            onRun={() => onRun(assemblyStep.key, buildParams)}
            onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            onGoFields={onGoFields}
          />
          <BuildSummaryAside
            scriptPath={scriptPath}
            source={scriptSource}
            runtimePath={finalRuntime}
            runtimePathExists={runtimePathExists}
            includeRuntime={includeRuntime}
            runtimeSize={finalRuntimeSize}
            runDone={runDone}
          />
          <BuildReadinessAside
            hasScript={!!scriptPath}
            hasRuntime={!!finalRuntime}
            runtimePathExists={runtimePathExists}
            runDone={runDone}
          />
        </>
      }
    />
  );
}

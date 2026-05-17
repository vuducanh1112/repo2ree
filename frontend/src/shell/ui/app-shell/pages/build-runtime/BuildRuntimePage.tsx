import { useCallback, useMemo, useState } from "react";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import type { BuildScriptSource } from "../../../../../core/ree-assembly/buildRuntimeUiState";
import {
  buildFooterHint,
  buildRunStatusLabel,
  deriveRuntimeFileSize,
} from "../../../../../core/ree-assembly/buildRuntimeUiState";
import {
  removeWorkspaceFileByPath,
  upsertWorkspaceFileByPath,
} from "../../../../../core/workspace/fileTreeOps";
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
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { PAGE } from "../../state/pages";
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
      const withoutPrevious =
        previousPath && previousPath !== path
          ? removeWorkspaceFileByPath(files, previousPath)
          : files;
      upsertWorkspaceFileByPath(withoutPrevious, path, content, { tag: PAGE.SOURCE });
      onReeSpecChange?.((current) => ({ ...current, build_runtime_script: path }));
      void onPersistWorkspaceFile?.(previousPath, path, content);
    },
    [files, onPersistWorkspaceFile, onReeSpecChange, scriptPath],
  );

  const handleClearScript = useCallback(() => {
    onReeSpecChange?.((current) => ({ ...current, build_runtime_script: "" }));
  }, [onReeSpecChange]);

  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
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

  const runtimeHint = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";

  const hasScript = !!scriptPath;
  const statusLabel = buildRunStatusLabel({ running, runDone, hasScript });

  const headerBadges = (
    <>
      {scriptPath && <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>}
      <span style={lgStatusBadge(runDone)}>{statusLabel}</span>
      {runDone && badge && (
        <span style={lgOutcomeBadge(badge.color, badge.bg)}>
          {Ic.check(11)} {badge.label}
        </span>
      )}
    </>
  );

  const headerRight =
    runDone && ts ? (
      <span
        style={{
          fontSize: 11,
          color: lgColors.textMuted,
          fontFamily: F.mono,
          flexShrink: 0,
        }}
      >
        Last built{" "}
        {new Date(ts).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })}
      </span>
    ) : null;

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.cpu(24)}
          iconTint={{
            color: assemblyStep.color,
            border: `${assemblyStep.color}55`,
            shadow: `${assemblyStep.color}28`,
          }}
          title={assemblyStep.label}
          subtitle={assemblyStep.desc}
          badges={headerBadges}
          right={headerRight}
        />

        <div style={lgStyles.mainGrid}>
          <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
            <div style={lgStyles.sectionBody}>
              <div style={lgStyles.sectionHeader}>
                <div
                  style={{
                    ...lgStyles.sectionIcon,
                    color: assemblyStep.color,
                    border: `1px solid ${assemblyStep.color}48`,
                  }}
                >
                  {Ic.terminal(19)}
                </div>
                <div>
                  <h2 style={lgStyles.sectionTitle}>Build Script</h2>
                  <div style={lgStyles.sectionSubtitle}>
                    One script — pick existing, write your own, or generate from a base.
                  </div>
                </div>
              </div>

              <BuildScriptCard
                scriptPath={scriptPath}
                scriptContent={scriptContent}
                source={scriptSource}
                runtimeHint={runtimeHint}
                files={files}
                onCommit={handleCommitScript}
                onClear={handleClearScript}
                onSourceChange={setScriptSource}
              />

              <div style={{ marginTop: 22 }}>
                <div style={lgStyles.sectionHeader}>
                  <div
                    style={{
                      ...lgStyles.sectionIcon,
                      color: assemblyStep.color,
                      border: `1px solid ${assemblyStep.color}48`,
                    }}
                  >
                    {Ic.archive(19)}
                  </div>
                  <div>
                    <h2 style={lgStyles.sectionTitle}>Runtime Artifact</h2>
                    <div style={lgStyles.sectionSubtitle}>
                      The file produced by your build, consumed by SBOM and activation.
                    </div>
                  </div>
                </div>

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

          <aside style={lgStyles.aside}>
            <BuildRunConsole
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
          </aside>
        </div>
      </div>
    </div>
  );
}

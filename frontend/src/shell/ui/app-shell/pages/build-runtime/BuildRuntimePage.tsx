import type { ReeAssemblyRunParams } from "@core/ree-assembly/assemblyTypes";
import type { BuildScriptSource } from "@core/ree-assembly/buildRuntimeUiState";
import {
  buildFooterHint,
  buildRunStatusLabel,
  deriveRuntimeFileSize,
  resolvedRuntimePath,
} from "@core/ree-assembly/buildRuntimeUiState";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgOutcomeBadge,
  lgPageColors,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useMemo, useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { RunActionButton } from "../../components/RunActionButton";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { BuildLogCard, BuildScriptCard, RuntimeArtifactCard } from "./sections";

const BUILD_PAGE_COLOR = lgPageColors.runtimeEnv;

function BuildRunControls({
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
      label={running ? "Building…" : runDone ? "Re-build" : "Run build"}
      running={running}
      disabled={disabled}
      onRun={onRun}
      onCancel={onCancel}
    />
  );
}

export function PageBuildRuntime({
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
  const finalRuntimeFile = useMemo(
    () => (finalRuntime ? findFileByPath(files, finalRuntime) : null),
    [files, finalRuntime],
  );
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  const hasScript = !!scriptPath;
  const hasMissing = missing.length > 0;
  const statusLabel = buildRunStatusLabel({ running, runDone, hasScript });

  return (
    <div style={pageRoot}>
      <GlassPageHeader
        icon={Ic.cpu(24)}
        iconTint={{
          color: BUILD_PAGE_COLOR,
          border: `${BUILD_PAGE_COLOR}55`,
          shadow: `${BUILD_PAGE_COLOR}28`,
        }}
        title="Build Runtime"
        subtitle="Write or pick the build script that produces the runtime artifact."
        badges={
          <>
            {scriptPath && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>
            )}
            <span style={lgStatusBadge(runDone)}>{statusLabel}</span>
            {runDone && badge && (
              <span style={lgOutcomeBadge(badge.color, badge.bg)}>
                {Ic.check(11)} {badge.label}
              </span>
            )}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last built" ts={ts} />}
            <BuildRunControls
              running={running}
              runDone={runDone}
              disabled={running || hasMissing}
              onRun={() => onRun(assemblyStep.key, buildParams)}
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
              icon={Ic.terminal(19)}
              color={BUILD_PAGE_COLOR}
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
                color={BUILD_PAGE_COLOR}
                title="Runtime Artifact"
                subtitle="The file produced by your build, consumed by SBOM and activation."
              />

              <RuntimeArtifactCard
                runtimePath={finalRuntime}
                runtimeSize={finalRuntimeSize}
                runtimePathExists={runtimePathExists}
                files={files}
                onRuntimeChange={handleRuntimeChange}
              />
            </div>

            <BuildLogCard log={log} running={running} ts={ts} />
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
              {buildFooterHint({ runDone, hasScript })}
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

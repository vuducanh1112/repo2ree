import { RESERVED_BUILD_SCRIPT } from "@core/ree/ReeSpec";
import {
  buildFooterHint,
  buildRunStatusLabel,
  deriveRuntimeFileSize,
  resolvedRuntimePath,
} from "@core/ree-assembly/buildRuntimeUiState";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgPageColors,
  lgPageRoot,
  lgPillChip,
  lgStatusBadge,
  pageIconTint,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useMemo } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { GlassSubPanel } from "../../components/GlassSubPanel";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { BuildLogCard, ReservedBuildScriptCard, RuntimeArtifactCard } from "./sections";

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
  runFailed,
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

  const scriptPath = RESERVED_BUILD_SCRIPT;
  const scriptFile = useMemo(() => findFileByPath(files, RESERVED_BUILD_SCRIPT), [files]);
  const scriptContent = scriptFile?.content || "";

  // Save a file to the overlay — does not change the selected build script.
  const handleSaveFile = useCallback(
    (previousPath: string | undefined, path: string, content: string) => {
      void onPersistWorkspaceFile?.(previousPath, path, content);
    },
    [onPersistWorkspaceFile],
  );

  const handleSaveReservedBuildScript = useCallback(
    (content: string) => {
      handleSaveFile(undefined, RESERVED_BUILD_SCRIPT, content);
    },
    [handleSaveFile],
  );

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimeFile = useMemo(
    () => (runtimePath ? findFileByPath(files, runtimePath) : null),
    [files, runtimePath],
  );
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeSize = useMemo(() => deriveRuntimeFileSize(runtimeFile), [runtimeFile]);

  const handleRuntimeChange = useCallback(
    (path: string) => onReeSpecChange?.((current) => ({ ...current, runtime: path })),
    [onReeSpecChange],
  );

  // The reserved build script is seeded empty; an authored (non-empty) script
  // is what makes the build runnable.
  const hasScript = scriptContent.trim().length > 0;
  const hasMissing = missing.length > 0;
  const statusLabel = buildRunStatusLabel({ running, runDone, runFailed, hasScript });

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={Ic.cpu(24)}
        iconTint={pageIconTint(BUILD_PAGE_COLOR)}
        title="Build Runtime"
        subtitle="Build or acquire an environment, connect the workspace, then give experiments a reusable run target."
        badges={
          <>
            {scriptPath && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>
            )}
            <span style={lgStatusBadge(runDone && !runFailed)}>{statusLabel}</span>
            {badge && <OutcomeBadge badge={badge} />}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last built" ts={ts} />}
            <BuildRunControls
              running={running}
              runDone={runDone}
              disabled={running || hasMissing || !hasScript}
              onRun={() => onRun(assemblyStep.key, params)}
              onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            />
          </div>
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.archive(19)}
            color={BUILD_PAGE_COLOR}
            title="1. Build or acquire the runtime"
            subtitle="Choose the artifact that will execute this REE. Build from the workspace now, or select an artifact obtained elsewhere."
          />
          <div style={{ marginTop: 10 }}>
            <RuntimeArtifactCard
              runtimePath={runtimePath}
              runtimeSize={runtimeSize}
              runtimePathExists={runtimePathExists}
              files={files}
              onRuntimeChange={handleRuntimeChange}
            />
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.file(19)}
            color={BUILD_PAGE_COLOR}
            title="Build recipe"
            subtitle="Edit REE’s reserved build program. It can call any build scripts already supplied by the project."
          />
          <div style={{ marginTop: 10 }}>
            <ReservedBuildScriptCard
              currentContent={scriptContent}
              onSave={handleSaveReservedBuildScript}
            />
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
          <BuildLogCard log={log} running={running} ts={ts} />
        </GlassSubPanel>

        <GlassPanelFooter bar>
          {buildFooterHint({ runDone, runFailed, hasScript })}
        </GlassPanelFooter>
      </div>
    </div>
  );
}

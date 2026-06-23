import type { RuntimeEntry } from "@core/ree/ReeSpec";
import type { ReeAssemblyRunParams } from "@core/ree-assembly/assemblyTypes";
import { buildFooterHint, buildRunStatusLabel } from "@core/ree-assembly/buildRuntimeUiState";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgOutcomeBadge,
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
import { RunActionButton } from "../../components/RunActionButton";
import { SubstratePicker } from "../../components/SubstratePicker";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { BuildLogCard, BuildScriptCard } from "./sections";

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

  const buildParams: ReeAssemblyRunParams<"build"> = {
    ...(params as ReeAssemblyRunParams<"build">),
    build_runtime_script_path: scriptPath,
  };

  // Save a file to the overlay — does not change the selected build script.
  const handleSaveFile = useCallback(
    (previousPath: string | undefined, path: string, content: string) => {
      void onPersistWorkspaceFile?.(previousPath, path, content);
    },
    [onPersistWorkspaceFile],
  );

  // Explicitly select an existing workspace file as the active build script.
  const handleSelectScript = useCallback(
    (path: string) => {
      onReeSpecChange?.((current) => ({ ...current, build_runtime_script: path }));
    },
    [onReeSpecChange],
  );

  const handleClearScript = useCallback(() => {
    onReeSpecChange?.((current) => ({ ...current, build_runtime_script: "" }));
  }, [onReeSpecChange]);

  const runtimeEntry = ree.runtime_entry;

  const handleEntryChange = useCallback(
    (entry: RuntimeEntry) => onReeSpecChange?.((current) => ({ ...current, runtime_entry: entry })),
    [onReeSpecChange],
  );

  const hasScript = !!scriptPath;
  const hasMissing = missing.length > 0;
  const statusLabel = buildRunStatusLabel({ running, runDone, hasScript });

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={Ic.cpu(24)}
        iconTint={pageIconTint(BUILD_PAGE_COLOR)}
        title="Build Runtime"
        subtitle="Select the substrate, declare the artifact, and run the build script."
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

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.cpu(19)}
            color={BUILD_PAGE_COLOR}
            title="Substrate"
            subtitle="Pick how the workbench enters the runtime. The same choice drives which build script applies below."
          />
          <div style={{ marginTop: 10 }}>
            {/* Compact selector only — the build script gets its own subpanel
                below rather than being nested inside the substrate row. */}
            <SubstratePicker
              entry={runtimeEntry}
              accent={BUILD_PAGE_COLOR}
              onChange={handleEntryChange}
              renderDetail={() => null}
            />
          </div>
        </GlassSubPanel>

        {/* The build script's Create / Edit / Active sections each render as their
            own subpanel, sitting as siblings alongside Substrate and Build Log. */}
        <BuildScriptCard
          scriptPath={scriptPath}
          scriptContent={scriptContent}
          runtimeEntry={runtimeEntry}
          files={files}
          onSaveFile={handleSaveFile}
          onSelectScript={handleSelectScript}
          onClearScript={handleClearScript}
        />

        <GlassSubPanel>
          <BuildLogCard log={log} running={running} ts={ts} />
        </GlassSubPanel>

        <GlassPanelFooter bar>{buildFooterHint({ runDone, hasScript })}</GlassPanelFooter>
      </div>
    </div>
  );
}

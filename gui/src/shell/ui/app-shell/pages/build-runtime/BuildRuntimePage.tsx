import { PAGE } from "@core/app-shell/pages";
import {
  buildFooterHint,
  buildRunStatusLabel,
  canRunBuild,
  deriveRuntimeFileSize,
  resolvedRuntimePath,
} from "@core/ree-steps/buildRuntimeUiState";
import { findFileByWorkspacePath, workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { useGenerateBuildScript } from "@shell/data/scriptInference/mutations";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { Ic } from "@shell/ui/shared/components/Icon";
import { stageTone } from "@shell/ui/theme/appearance";
import { lgPageRoot, lgPillChip, lgStatusBadge } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useMemo, useState } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GenerateScriptControl } from "../../components/GenerateScriptControl";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { GlassSubPanel } from "../../components/GlassSubPanel";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import type { StepPageProps } from "../sharedStepUi";
import { ReservedBuildScriptCard, RuntimeArtifactCard } from "./sections";

const BUILD_PAGE_COLOR = stageTone(PAGE.BUILD);

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
  step,
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
}: StepPageProps) {
  const files = workspaceFiles || [];

  // The reserved build-script path and template variants are backend-owned;
  // the file itself arrives seeded with the default template.
  const { data: templateCatalog } = useScriptTemplates();
  const scriptPath = templateCatalog?.build.path ?? "";
  const scriptFile = useMemo(
    () => (scriptPath ? findFileByWorkspacePath(files, scriptPath) : null),
    [files, scriptPath],
  );
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
      if (!scriptPath) return;
      handleSaveFile(undefined, scriptPath, content);
    },
    [handleSaveFile, scriptPath],
  );

  // Read-only inference: generate a candidate build script from the repository
  // and load it into the editor. It is never written here — the author reviews
  // it and clicks Save build script (exactly like editing by hand). The shared
  // GenerateScriptControl renders the button, status, and decision graph.
  const generate = useGenerateBuildScript();
  const [externalEdit, setExternalEdit] = useState<
    { content: string; nonce: number } | undefined
  >();
  const loadGenerated = useCallback(
    (body: string) => setExternalEdit((prev) => ({ content: body, nonce: (prev?.nonce ?? 0) + 1 })),
    [],
  );

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimeFile = useMemo(
    () => (runtimePath ? findFileByWorkspacePath(files, runtimePath) : null),
    [files, runtimePath],
  );
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeSize = useMemo(() => deriveRuntimeFileSize(runtimeFile), [runtimeFile]);

  const handleRuntimeChange = useCallback(
    (path: string) => onReeSpecChange?.((current) => ({ ...current, runtime: path })),
    [onReeSpecChange],
  );

  // The reserved build script arrives seeded with the starter template, so
  // this gate only blocks running before the workspace files have loaded (or
  // if the author blanked the script).
  const hasScript = scriptContent.trim().length > 0;
  const hasMissing = missing.length > 0;
  const statusLabel = buildRunStatusLabel({ running, runDone, runFailed, hasScript });
  // The build now needs the path it is expected to produce: the backend refuses
  // to start without a declared runtime_path, so the button says so here rather
  // than letting the run fail its precondition.
  const canRun = canRunBuild({ running, hasMissing, hasScript, hasRuntimePath: !!runtimePath });

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={Ic.cpu(24)}
        tint={BUILD_PAGE_COLOR}
        title="Build Runtime"
        subtitle="Declare where the build writes its runtime, author the build recipe, then run it to give experiments a reusable run target."
        badges={
          <>
            {scriptPath && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{scriptPath}</span>
            )}
            <span style={lgStatusBadge(runDone && !runFailed)}>{statusLabel}</span>
            {badge && <OutcomeBadge outcome={badge} />}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last built" ts={ts} />}
            <BuildRunControls
              running={running}
              runDone={runDone}
              disabled={!canRun}
              onRun={() => onRun(step.key, params)}
              onCancel={onCancel ? () => onCancel(step.key) : undefined}
            />
          </div>
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.archive(19)}
            tint={BUILD_PAGE_COLOR}
            title="1. Declare the runtime the build produces"
            subtitle="Name the path the build script writes its runtime to. The build refuses to run until it is declared, and fails if nothing lands there."
          />
          <div style={{ marginTop: 10 }}>
            <RuntimeArtifactCard
              runtimePath={runtimePath}
              runtimeSize={runtimeSize}
              runtimePathExists={runtimePathExists}
              onRuntimeChange={handleRuntimeChange}
            />
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.file(19)}
            tint={BUILD_PAGE_COLOR}
            title="Build recipe"
            subtitle="Edit REE’s reserved build program. It can call any build scripts already supplied by the project."
          />
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            <GenerateScriptControl
              generate={generate}
              onLoad={loadGenerated}
              noun="build script"
              notInferredHint="No clear Dockerfile or requirements.txt was found, or the layout is ambiguous."
              disabled={!scriptPath}
            />
            <ReservedBuildScriptCard
              currentContent={scriptContent}
              // Disabled until the catalog delivers the reserved path: an
              // enabled editor without a save destination would let edits
              // race the fetch (and silently drop the save).
              disabled={!scriptPath}
              templates={templateCatalog?.build.templates}
              externalEdit={externalEdit}
              onSave={handleSaveReservedBuildScript}
            />
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
          <CollapsibleLogCard log={log} running={running} title="Build log" />
        </GlassSubPanel>

        <GlassPanelFooter bar>
          {buildFooterHint({ runDone, runFailed, hasScript, hasRuntimePath: !!runtimePath })}
        </GlassPanelFooter>
      </div>
    </div>
  );
}

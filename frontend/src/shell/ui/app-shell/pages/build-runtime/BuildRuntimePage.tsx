import {
  buildFooterHint,
  buildRunStatusLabel,
  deriveRuntimeFileSize,
  resolvedRuntimePath,
} from "@core/ree-steps/buildRuntimeUiState";
import { findFileByWorkspacePath, workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import type { GeneratedBuildScript } from "@shell/data/scriptInference/buildCandidate";
import { useGenerateBuildScript } from "@shell/data/scriptInference/mutations";
import { renderDecisionDiagram, renderDecisionTrace } from "@shell/data/scriptInference/traceAscii";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgGlassButton,
  lgPageColors,
  lgPageRoot,
  lgPillChip,
  lgStatusBadge,
  pageIconTint,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useMemo, useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { GlassSubPanel } from "../../components/GlassSubPanel";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { RunActionButton } from "../../components/RunActionButton";
import type { StepPageProps } from "../sharedStepUi";
import { BuildLogCard, ReservedBuildScriptCard, RuntimeArtifactCard } from "./sections";

const BUILD_PAGE_COLOR = lgPageColors.runtimeEnv;

type GenerateStatus = { tone: "ok" | "warn" | "info" | "error"; message: string };

function genStatusColor(tone: GenerateStatus["tone"]): string {
  if (tone === "error") return lgColors.danger;
  if (tone === "warn") return lgColors.warning;
  if (tone === "info") return lgColors.suggestionText;
  return lgColors.success;
}

// One human sentence describing what was loaded and what the author must still
// weigh before saving — a decision (several strategies) and/or a strategy that
// warrants confirmation before it is kept.
function buildGenerateMessage(script: GeneratedBuildScript): string {
  const parts = [`Loaded a generated build script (${script.ruleId}).`];
  if (script.alternativeCount > 1) {
    parts.push(
      `${script.alternativeCount} runtime strategies were available — review before saving.`,
    );
  }
  if (script.application === "confirmation_required") {
    parts.push("This is a suggested strategy; confirm it fits before saving.");
  }
  parts.push("Review it, then click Save build script to keep it.");
  return parts.join(" ");
}

// The decision graph as monospace ASCII, collapsed by default: the static
// decision DAG with the run's path overlaid — why inference did (or did not)
// produce a script.
function DecisionTraceBlock({ text }: { text: string }) {
  return (
    <details style={{ marginTop: 2 }}>
      <summary
        style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: lgColors.textMuted }}
      >
        Decision graph
      </summary>
      <pre
        style={{
          margin: "8px 0 0",
          padding: "10px 12px",
          overflowX: "auto",
          borderRadius: 8,
          background: "rgba(15, 23, 42, 0.04)",
          border: "1px solid rgba(125, 211, 252, 0.35)",
          fontFamily: F.mono,
          fontSize: 11.5,
          lineHeight: 1.5,
          color: lgColors.textMid,
          whiteSpace: "pre",
        }}
      >
        {text}
      </pre>
    </details>
  );
}

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
  // it and clicks Save build script (exactly like editing by hand).
  const generate = useGenerateBuildScript();
  const [externalEdit, setExternalEdit] = useState<
    { content: string; nonce: number } | undefined
  >();
  const [genStatus, setGenStatus] = useState<GenerateStatus | null>(null);
  const [traceText, setTraceText] = useState<string | null>(null);

  const handleGenerate = useCallback(() => {
    setGenStatus(null);
    generate.mutate(undefined, {
      onSuccess: ({ generation, trace, dag }) => {
        // The decision graph explains the outcome either way (inferred or not):
        // the full static DAG with the traversed path overlaid when it shipped,
        // else just the traversed trace.
        setTraceText(
          dag && trace
            ? renderDecisionDiagram(dag, trace)
            : trace
              ? renderDecisionTrace(trace)
              : null,
        );
        if (generation.status === "not_inferred") {
          setGenStatus({
            tone: "warn",
            message:
              "No build script could be inferred from the repository (no clear Dockerfile or requirements.txt, or an ambiguous layout). See the decision trace below.",
          });
          return;
        }
        const script = generation.script;
        setExternalEdit((prev) => ({ content: script.body, nonce: (prev?.nonce ?? 0) + 1 }));
        setGenStatus({
          tone: script.application === "confirmation_required" ? "info" : "ok",
          message: buildGenerateMessage(script),
        });
      },
      onError: (error) => {
        setTraceText(null);
        setGenStatus({
          tone: "error",
          message: `Generation failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      },
    });
  }, [generate]);

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
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={generate.isPending || !scriptPath}
                title="Infer a build script from the repository (Dockerfile or requirements.txt). It loads into the editor below; nothing is saved until you click Save build script."
                style={{
                  ...lgGlassButton(),
                  padding: "6px 12px",
                  fontSize: 12,
                  fontWeight: 700,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  opacity: generate.isPending || !scriptPath ? 0.55 : 1,
                  cursor: generate.isPending || !scriptPath ? "not-allowed" : "pointer",
                }}
              >
                {generate.isPending ? Ic.loader(14) : Ic.fileCode(14)}
                {generate.isPending ? "Generating…" : "Generate from repository"}
              </button>
              {genStatus && (
                <span style={{ fontSize: 12, color: genStatusColor(genStatus.tone) }}>
                  {genStatus.message}
                </span>
              )}
            </div>
            {traceText && <DecisionTraceBlock text={traceText} />}
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
          <BuildLogCard log={log} running={running} ts={ts} />
        </GlassSubPanel>

        <GlassPanelFooter bar>
          {buildFooterHint({ runDone, runFailed, hasScript })}
        </GlassPanelFooter>
      </div>
    </div>
  );
}

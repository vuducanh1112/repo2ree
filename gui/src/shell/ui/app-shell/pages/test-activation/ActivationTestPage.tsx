import { createEmptyReeActivation, type ReeActivation } from "@core/ree/ReeSpec";
import {
  activationFooterHint,
  activationRunLabel,
  canRunActivation,
} from "@core/ree-steps/activationUiState";
import { resolvedRuntimePath } from "@core/ree-steps/buildRuntimeUiState";
import { findSbomArtifact, resolvedSbomPath } from "@core/ree-steps/sbomUiState";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import { findFileByWorkspacePath, workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { useGenerateActivationScript } from "@shell/data/scriptInference/mutations";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgPageRoot,
  lgPillChip,
  lgStatusBadge,
  pageIconTint,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useState } from "react";
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
import { RunScriptCard } from "../../components/RunScriptCard";
import type { StepPageProps } from "../sharedStepUi";
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
  step,
  ree,
  workspaceFiles,
  reeFiles,
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
  // Backend-owned starter templates; the verify editor prefills from the
  // default verify template until a script exists.
  const { data: templates } = useScriptTemplates();

  // Read-only inference: generate an activation scaffold from the built runtime
  // and load it into the editor. Never written here — the author reviews and
  // saves it exactly like editing by hand.
  const generateActivation = useGenerateActivationScript();
  const [activationExternalEdit, setActivationExternalEdit] = useState<
    { content: string; nonce: number } | undefined
  >();

  const activation: ReeActivation = ree.activation ?? createEmptyReeActivation();
  // The backend settles the activation run-script path on the intent; the
  // catalog covers the moment before that lands and the not-yet-declared
  // verify script.
  const activationScriptPath =
    activation.runScript || (templates?.activation.run_script_path ?? "");
  const activationScriptContent =
    findFileByWorkspacePath(files, activationScriptPath)?.content ?? "";
  const activationVerifyScriptPath =
    activation.verifyScript || (templates?.activation.verify_script_path ?? "");
  const activationVerifyScriptContent =
    findFileByWorkspacePath(files, activationVerifyScriptPath)?.content ?? "";

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomPathExists = !!findSbomArtifact(reeFiles, sbomPath);

  const activationParams: ReeStepRunParams<"activation"> = params as ReeStepRunParams<"activation">;

  const canRun = canRunActivation({
    running,
    hasMissing: missing.length > 0,
    runtimePathExists,
  });
  const activationReady = runDone && !runFailed && canRun;

  const handleSaveScript = useCallback(
    (content: string) => {
      if (!activationScriptPath) return;
      void onPersistWorkspaceFile?.(undefined, activationScriptPath, content);
      if (activation.runScript !== activationScriptPath) {
        onReeSpecChange?.((current) => ({
          ...current,
          activation: { ...current.activation, runScript: activationScriptPath },
        }));
      }
    },
    [onPersistWorkspaceFile, onReeSpecChange, activationScriptPath, activation.runScript],
  );

  // Saving a verify script declares it on the intent; until then activation's
  // verdict is its run script's exit code alone.
  const handleSaveVerifyScript = useCallback(
    (content: string) => {
      if (!activationVerifyScriptPath) return;
      void onPersistWorkspaceFile?.(undefined, activationVerifyScriptPath, content);
      if (activation.verifyScript !== activationVerifyScriptPath) {
        onReeSpecChange?.((current) => ({
          ...current,
          activation: { ...current.activation, verifyScript: activationVerifyScriptPath },
        }));
      }
    },
    [onPersistWorkspaceFile, onReeSpecChange, activationVerifyScriptPath, activation.verifyScript],
  );

  const commandLabel = activationScriptPath;

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={Ic.shield(24)}
        iconTint={pageIconTint(ACTIVATION_PAGE_COLOR)}
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
            {badge && <OutcomeBadge outcome={badge} />}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last verified" ts={ts} />}
            <ActivationRunControls
              running={running}
              runDone={runDone}
              disabled={!canRun}
              onRun={() => onRun(step.key, activationParams)}
              onCancel={onCancel ? () => onCancel(step.key) : undefined}
            />
          </div>
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        <GlassSubPanel>
          <GlassSectionHeader
            icon={Ic.shield(19)}
            color={ACTIVATION_PAGE_COLOR}
            title="Activation Run Script"
            subtitle="Activation owns its run script: it fully defines how the runtime is entered and probed for liveness."
          />

          <div style={{ marginTop: 10 }}>
            <RunScriptCard
              scriptPath={activationScriptPath}
              currentContent={activationScriptContent}
              disabled={!activationScriptPath}
              label="Activation run script"
              helper="Saved to the workspace overlay and run from the workspace root."
              templates={templates?.activation.templates}
              externalEdit={activationExternalEdit}
              generateSlot={
                <GenerateScriptControl
                  generate={generateActivation}
                  noun="activation script"
                  disabled={!activationScriptPath}
                  onLoad={(body) =>
                    setActivationExternalEdit((prev) => ({
                      content: body,
                      nonce: (prev?.nonce ?? 0) + 1,
                    }))
                  }
                />
              }
              onSave={handleSaveScript}
            />
          </div>

          <div style={{ marginTop: 10 }}>
            <RunScriptCard
              scriptPath={activationVerifyScriptPath}
              currentContent={activationVerifyScriptContent}
              disabled={!activationVerifyScriptPath}
              label="Activation verify script (optional)"
              helper="Checks the activation run afterwards — a plain script run from the workspace root, reading outputs straight from the workspace; its exit code is the verdict. Without one, the run script's exit code decides."
              templates={templates?.verify}
              saveButtonContent="Save verify script"
              savedLabel="Saved verify script"
              unsavedLabel="Unsaved verify script"
              onSave={handleSaveVerifyScript}
            />
          </div>
        </GlassSubPanel>

        <GlassSubPanel>
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
        </GlassSubPanel>

        <GlassSubPanel>
          <CollapsibleLogCard
            log={log}
            running={running}
            title={ts ? "Activation log" : "Activation logs"}
          />
        </GlassSubPanel>

        <GlassPanelFooter bar>{activationFooterHint({ runDone, runFailed })}</GlassPanelFooter>
      </div>
    </div>
  );
}

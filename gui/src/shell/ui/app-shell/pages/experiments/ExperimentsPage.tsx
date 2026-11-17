import {
  addExperiment as coreAddExperiment,
  removeExperiment as coreRemoveExperiment,
  patchExperiment,
} from "@core/ree/experimentOps";
import { experimentIndexFromField, experimentValidation } from "@core/ree/experimentRules";
import type { ReeExperiment, ReeSpec } from "@core/ree/ReeSpec";
import { findFileByWorkspacePath } from "@core/workspace/fileTreeTraversal";
import { useScriptTemplates } from "@shell/data/scriptTemplates/catalog";
import { experimentRunScriptPath } from "@shell/data/scriptTemplates/paths";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import { useEffect, useRef, useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPageShell, GlassPanel, GlassSectionBody } from "../../components/GlassPageShell";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import type { PageExperimentsProps } from "../sharedStepUi";
import styles from "./ExperimentsPage.module.css";
import {
  ExperimentCardList,
  ExperimentDetail,
  ExperimentHeaderActions,
  ExperimentQuickAdd,
  type ExperimentSuggestion,
  ExperimentsCoverageTally,
} from "./ExperimentsPageSections";
import { useExperimentRun } from "./useExperimentRun";

// A starter run script seeded from a quick-add suggestion's sample command.
function suggestionTemplate(command: string): string {
  return `#!/usr/bin/env sh
set -eu

# Adapt this so it runs inside your built runtime (e.g. wrap it in docker run).
${command}
`;
}

// ================================================
// Page component
// ================================================

export function PageExperiments({
  reeId,
  reeSpec,
  locked,
  onReeChange,
  onFocusedFieldChange,
  onBeforeRun,
  focusedField,
  workspaceFiles,
  onPersistWorkspaceFile,
}: PageExperimentsProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  // Backend-owned path conventions, needed to seed a suggestion's run script.
  const { data: templates } = useScriptTemplates();

  // External navigation can deep-link into a specific experiment by setting
  // focusedField. Apply it only when it changes, so manual card selection on
  // this page isn't clobbered.
  const appliedField = useRef<string | null>(null);
  useEffect(() => {
    if (focusedField === appliedField.current) return;
    appliedField.current = focusedField;
    setSelectedIndex(experimentIndexFromField(focusedField));
  }, [focusedField]);

  // ================================================
  // Derived state
  // ================================================

  const experiments: ReeExperiment[] = reeSpec.experiments || [];

  const updateExperiment = (index: number, patch: Partial<ReeExperiment>) => {
    if (locked) return;
    onReeChange((current) => patchExperiment(current, index, patch));
  };

  const addExperiment = () => {
    if (locked) return;
    const newIndex = experiments.length;
    onReeChange((current) => coreAddExperiment(current));
    setSelectedIndex(newIndex);
    onFocusedFieldChange(`experiments[${newIndex}].name`);
  };

  const addFromSuggestion = (suggestion: ExperimentSuggestion) => {
    // The catalog is fetched once per session; a click before it lands would
    // have no path to seed the script at, so treat it like locked.
    if (locked || !templates) return;
    const newIndex = experiments.length;
    const scriptPath = experimentRunScriptPath(templates, suggestion.name);
    onReeChange((current: ReeSpec) =>
      patchExperiment(coreAddExperiment(current), newIndex, {
        name: suggestion.name,
        description: suggestion.description,
        runScript: scriptPath,
      }),
    );
    // The suggested command is the script's starting point; the author adapts it
    // to enter their runtime (e.g. wrapping it in `docker run …`).
    setSuggestedScripts((pending) => ({
      ...pending,
      [scriptPath]: suggestionTemplate(suggestion.command),
    }));
    setSelectedIndex(newIndex);
    onFocusedFieldChange(`experiments[${newIndex}].name`);
  };

  const removeExperiment = (index: number) => {
    if (locked) return;
    onReeChange((current) => coreRemoveExperiment(current, index));
    if (selectedIndex === index) {
      setSelectedIndex(null);
      onFocusedFieldChange(null);
    }
  };

  const selectedExperiment = selectedIndex !== null ? (experiments[selectedIndex] ?? null) : null;

  const otherNames =
    selectedIndex === null
      ? []
      : experiments
          .filter((_, i) => i !== selectedIndex)
          .map((e) => e.name.trim())
          .filter(Boolean);

  // Declaring an experiment gives it its scripts, so a suggestion's command is
  // written once the declaration has brought the run script into the workspace.
  const [suggestedScripts, setSuggestedScripts] = useState<Record<string, string>>({});
  const persistRef = useRef(onPersistWorkspaceFile);
  persistRef.current = onPersistWorkspaceFile;
  useEffect(() => {
    const files = workspaceFiles || [];
    const declared = Object.keys(suggestedScripts).filter((path) =>
      findFileByWorkspacePath(files, path),
    );
    if (declared.length === 0) return;
    for (const path of declared) void persistRef.current(path, suggestedScripts[path] ?? "");
    setSuggestedScripts((pending) =>
      Object.fromEntries(Object.entries(pending).filter(([path]) => !declared.includes(path))),
    );
  }, [suggestedScripts, workspaceFiles]);

  // Run lives here (not in the detail body) so its controls can sit in the
  // page header's top-right, while the detail body still shows the result.
  const run = useExperimentRun({
    reeId,
    experimentName: selectedExperiment?.name ?? null,
    onBeforeRun,
  });
  const canRun = selectedExperiment
    ? experimentValidation(selectedExperiment, otherNames).canRun
    : false;

  // ================================================
  // Coverage stats
  // ================================================

  // The three fields an experiment needs to be runnable and checkable. The
  // rest — description, runtime and resource estimates — are per-experiment
  // detail, reported on the experiment's own card rather than tallied here.
  const total = experiments.length;
  const withName = experiments.filter((e) => e.name.trim() !== "").length;
  const withCommand = experiments.filter((e) => e.runScript.trim() !== "").length;
  const withVerify = experiments.filter((e) => e.verifyScript.trim() !== "").length;

  // ================================================
  // Render
  // ================================================

  const headerBadges = (
    <>
      <Badge tone="info">
        {total} {total === 1 ? "experiment" : "experiments"}
      </Badge>
      <Badge tone={total > 0 ? "success" : "warning"}>{total > 0 ? "Defined" : "Empty"}</Badge>
    </>
  );

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.terminal(24)}
        title="Experiments"
        subtitle="Reproducibility verification commands recorded in the REE."
        badges={headerBadges}
        right={
          selectedExperiment !== null && selectedIndex !== null ? (
            <ExperimentHeaderActions
              locked={locked}
              canRun={canRun}
              isRunning={run.isRunning}
              onRun={() => run.startRun()}
              onCancel={() => run.cancelRun()}
              onRemove={() => removeExperiment(selectedIndex)}
            />
          ) : undefined
        }
      />

      <div className={styles.stack}>
        {selectedExperiment !== null && selectedIndex !== null ? (
          <ExperimentDetail
            experiment={selectedExperiment}
            index={selectedIndex}
            otherNames={otherNames}
            locked={locked}
            experimentEnvironmentPath={reeSpec.experimentEnvironmentPath || null}
            scriptContent={
              findFileByWorkspacePath(workspaceFiles, selectedExperiment.runScript)?.content ?? ""
            }
            verifyScriptContent={
              findFileByWorkspacePath(workspaceFiles, selectedExperiment.verifyScript)?.content ??
              ""
            }
            onUpdate={(patch) => updateExperiment(selectedIndex, patch)}
            onSaveScript={(path, content) => {
              void onPersistWorkspaceFile(path, content);
              if (path !== selectedExperiment.runScript) {
                updateExperiment(selectedIndex, { runScript: path });
              }
            }}
            onSaveVerifyScript={(path, content) => {
              void onPersistWorkspaceFile(path, content);
              if (path !== selectedExperiment.verifyScript) {
                updateExperiment(selectedIndex, { verifyScript: path });
              }
            }}
            onBack={() => {
              setSelectedIndex(null);
              onFocusedFieldChange(null);
            }}
            runState={run.runState}
          />
        ) : (
          <GlassPanel clipped>
            <GlassSectionBody>
              <GlassSectionHeader
                icon={Ic.layers(19)}
                title="Catalog"
                subtitle="Each experiment is a named, runnable check that proves the REE behaves as expected."
              />

              <ExperimentCardList
                experiments={experiments}
                locked={locked}
                onSelect={setSelectedIndex}
                onAdd={addExperiment}
                onRemove={removeExperiment}
              />

              {!locked && <ExperimentQuickAdd locked={locked} onAdd={addFromSuggestion} />}
            </GlassSectionBody>

            <GlassPanelFooter
              action={
                <div className={styles.footerActions}>
                  {!locked && (
                    <Button icon={Ic.plus(13)} onClick={addExperiment}>
                      Add experiment
                    </Button>
                  )}
                </div>
              }
            >
              {total === 0 ? (
                "Experiments are optional but raise the achievable reproducibility level."
              ) : (
                <>
                  {`${total} recorded. `}
                  <ExperimentsCoverageTally
                    total={total}
                    withName={withName}
                    withCommand={withCommand}
                    withVerify={withVerify}
                  />
                </>
              )}
            </GlassPanelFooter>
          </GlassPanel>
        )}
      </div>
    </GlassPageShell>
  );
}

import {
  addExperiment as coreAddExperiment,
  removeExperiment as coreRemoveExperiment,
  patchExperiment,
} from "@core/ree/experimentOps";
import { experimentScriptPath, type ReeExperiment, type ReeSpec } from "@core/ree/ReeSpec";
import { findFileByWorkspacePath } from "@core/workspace/fileTreeTraversal";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgGlassButton,
  lgNextButton,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { useEffect, useRef, useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { PAGE } from "../../state/pages";
import type { PageExperimentsProps } from "../sharedStepUi";
import {
  ExperimentCardList,
  ExperimentDetail,
  ExperimentHeaderActions,
  type ExperimentSuggestion,
  ExperimentsAboutAside,
  ExperimentsCoverageAside,
  ExperimentsSuggestionsAside,
} from "./ExperimentsPageSections";
import { experimentIndexFromField, experimentValidation } from "./experimentsPageHelpers";
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
  onGoPage,
  onFocusedFieldChange,
  onBeforeRun,
  focusedField,
  workspaceFiles,
  onPersistWorkspaceFile,
}: PageExperimentsProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  // The canvas deep-links into a specific experiment by setting focusedField
  // (e.g. when a satellite in the decompose view is clicked). Apply it only when
  // it changes, so manual card selection on this page isn't clobbered.
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
    if (locked) return;
    const newIndex = experiments.length;
    const scriptPath = experimentScriptPath(suggestion.name);
    onReeChange((current: ReeSpec) =>
      patchExperiment(coreAddExperiment(current), newIndex, {
        name: suggestion.name,
        description: suggestion.description,
        run_script: scriptPath,
      }),
    );
    // Seed the script with the suggested command as a starting point; the author
    // adapts it to enter their runtime (e.g. wrapping it in `docker run …`).
    void onPersistWorkspaceFile(undefined, scriptPath, suggestionTemplate(suggestion.command));
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

  const total = experiments.length;
  const withName = experiments.filter((e) => e.name.trim() !== "").length;
  const withCommand = experiments.filter((e) => e.run_script.trim() !== "").length;
  const withDescription = experiments.filter((e) => e.description.trim() !== "").length;
  const withVerify = experiments.filter((e) => e.verify_script.trim() !== "").length;
  const withRuntimeEstimate = experiments.filter((e) => e.runtime_estimate.trim() !== "").length;
  const withResourceEstimates = experiments.filter((e) =>
    Object.values(e.resource_estimates).some((value) => value.trim() !== ""),
  ).length;

  // ================================================
  // Render
  // ================================================

  const headerBadges = (
    <>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: lgColors.chipText,
          background: "rgba(239, 246, 255, 0.85)",
          border: "1px solid rgba(79, 70, 229, 0.28)",
          borderRadius: 99,
          padding: "3px 9px",
        }}
      >
        {total} {total === 1 ? "experiment" : "experiments"}
      </span>
      <span style={lgStatusBadge(total > 0)}>{total > 0 ? "Defined" : "Empty"}</span>
    </>
  );

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
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
                onRemove={() => removeExperiment(selectedIndex)}
              />
            ) : undefined
          }
        />

        <div style={lgStyles.mainGrid}>
          {selectedExperiment !== null && selectedIndex !== null ? (
            <ExperimentDetail
              experiment={selectedExperiment}
              index={selectedIndex}
              otherNames={otherNames}
              locked={locked}
              scriptContent={
                findFileByWorkspacePath(workspaceFiles, selectedExperiment.run_script)?.content ??
                ""
              }
              verifyScriptContent={
                findFileByWorkspacePath(workspaceFiles, selectedExperiment.verify_script)
                  ?.content ?? ""
              }
              onUpdate={(patch) => updateExperiment(selectedIndex, patch)}
              onSaveScript={(path, content) => {
                void onPersistWorkspaceFile(undefined, path, content);
                if (path !== selectedExperiment.run_script) {
                  updateExperiment(selectedIndex, { run_script: path });
                }
              }}
              onSaveVerifyScript={(path, content) => {
                void onPersistWorkspaceFile(undefined, path, content);
                if (path !== selectedExperiment.verify_script) {
                  updateExperiment(selectedIndex, { verify_script: path });
                }
              }}
              onBack={() => {
                setSelectedIndex(null);
                onFocusedFieldChange(null);
              }}
              runState={run.runState}
            />
          ) : (
            <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
              <div style={lgStyles.sectionBody}>
                <div style={lgStyles.sectionHeader}>
                  <div style={lgStyles.sectionIcon}>{Ic.layers(19)}</div>
                  <div>
                    <h2 style={lgStyles.sectionTitle}>Catalog</h2>
                    <div style={lgStyles.sectionSubtitle}>
                      Each experiment is a named, runnable check that proves the REE behaves as
                      expected.
                    </div>
                  </div>
                </div>

                <ExperimentCardList
                  experiments={experiments}
                  locked={locked}
                  onSelect={setSelectedIndex}
                  onAdd={addExperiment}
                  onRemove={removeExperiment}
                />
              </div>

              <div style={lgStyles.footer}>
                <span style={{ color: lgColors.textMuted, fontSize: 12 }}>
                  {total === 0
                    ? "Experiments are optional but raise the achievable reproducibility level."
                    : `${total} recorded — continue to deposit & share when ready.`}
                </span>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  {!locked && (
                    <button
                      type="button"
                      onClick={addExperiment}
                      style={{
                        ...lgGlassButton(),
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      {Ic.plus(13)} Add experiment
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onGoPage(PAGE.ARCHIVE)}
                    style={lgNextButton()}
                  >
                    Next: Deposit & Share {Ic.chevR(15)}
                  </button>
                </div>
              </div>
            </section>
          )}

          <aside style={lgStyles.aside}>
            <ExperimentsCoverageAside
              total={total}
              withName={withName}
              withCommand={withCommand}
              withDescription={withDescription}
              withVerify={withVerify}
              withRuntimeEstimate={withRuntimeEstimate}
              withResourceEstimates={withResourceEstimates}
            />
            <ExperimentsSuggestionsAside locked={locked} onAdd={addFromSuggestion} />
            <ExperimentsAboutAside />
          </aside>
        </div>
      </div>
    </div>
  );
}

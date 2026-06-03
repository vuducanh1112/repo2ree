import { useState } from "react";
import {
  addExperiment as coreAddExperiment,
  removeExperiment as coreRemoveExperiment,
  patchExperiment,
} from "../../../../../core/ree/experimentOps";
import type { ReeExperiment, ReeSpec } from "../../../../../core/ree/ReeSpec";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgGlassButton,
  lgNextButton,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { PAGE } from "../../state/pages";
import type { PageExperimentsProps } from "../sharedAssemblyUi";
import {
  ExperimentCardList,
  ExperimentDetail,
  type ExperimentSuggestion,
  ExperimentsAboutAside,
  ExperimentsCoverageAside,
  ExperimentsSuggestionsAside,
} from "./ExperimentsPageSections";

// ================================================
// Page component
// ================================================

export function PageExperiments({
  reeId,
  reeSpec,
  locked,
  onReeChange,
  onGoAssemblyPage,
  onFocusedFieldChange,
  onSnapshotComplete,
  onBeforeRun,
  focusedField: _focusedField,
}: PageExperimentsProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

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
    onReeChange((current: ReeSpec) =>
      patchExperiment(coreAddExperiment(current), newIndex, {
        name: suggestion.name,
        description: suggestion.description,
        command: suggestion.command,
      }),
    );
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

  // ================================================
  // Coverage stats
  // ================================================

  const total = experiments.length;
  const withName = experiments.filter((e) => e.name.trim() !== "").length;
  const withCommand = experiments.filter((e) => e.command.trim() !== "").length;
  const withDescription = experiments.filter((e) => e.description.trim() !== "").length;
  const withOutputs = experiments.filter((e) => (e.outputs?.length ?? 0) > 0).length;
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
        />

        <div style={lgStyles.mainGrid}>
          {selectedExperiment !== null && selectedIndex !== null ? (
            <ExperimentDetail
              reeId={reeId}
              experiment={selectedExperiment}
              index={selectedIndex}
              otherNames={experiments
                .filter((_, i) => i !== selectedIndex)
                .map((e) => e.name.trim())
                .filter(Boolean)}
              locked={locked}
              onUpdate={(patch) => updateExperiment(selectedIndex, patch)}
              onBack={() => {
                setSelectedIndex(null);
                onFocusedFieldChange(null);
              }}
              onRemove={() => removeExperiment(selectedIndex)}
              onSnapshotComplete={onSnapshotComplete}
              onBeforeRun={onBeforeRun}
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
                    onClick={() => onGoAssemblyPage(PAGE.ARCHIVE)}
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
              withOutputs={withOutputs}
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

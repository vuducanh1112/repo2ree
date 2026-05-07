import { useState } from "react";
import {
  addExperiment as coreAddExperiment,
  removeExperiment as coreRemoveExperiment,
  patchExperiment,
} from "../../../../../core/ree/experimentOps";
import type { ReeExperiment } from "../../../../../core/ree/ReeSpec";
import { Ic } from "../../../shared/components/Icon";
import { C } from "../../../theme/theme";
import { AssemblyPageHeader, NextStepNudge } from "../../components/pageChrome";
import type { PageExperimentsProps } from "../sharedAssemblyUi";
import { CatalogTable, ExperimentDetail } from "./ExperimentsPageSections";

export function PageExperiments({
  reeSpec,
  locked,
  badges,
  onReeChange,
  onGoAssemblyPage,
  onFocusedFieldChange,
  focusedField: _focusedField,
}: PageExperimentsProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

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

  const removeExperiment = (index: number) => {
    if (locked) return;
    onReeChange((current) => coreRemoveExperiment(current, index));
    setSelectedIndex(null);
    onFocusedFieldChange(null);
  };

  const selectedExperiment = selectedIndex !== null ? (experiments[selectedIndex] ?? null) : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        background: C.bg,
      }}
    >
      <AssemblyPageHeader
        color={C.accent}
        icon={Ic.terminal(16)}
        title="Experiments"
        subtitle="reproducibility verification commands"
      />

      {selectedExperiment !== null && selectedIndex !== null ? (
        <ExperimentDetail
          experiment={selectedExperiment}
          index={selectedIndex}
          locked={locked}
          onUpdate={(patch: Partial<ReeExperiment>) => updateExperiment(selectedIndex, patch)}
          onBack={() => {
            setSelectedIndex(null);
            onFocusedFieldChange(null);
          }}
          onRemove={() => removeExperiment(selectedIndex)}
        />
      ) : (
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <CatalogTable
            experiments={experiments}
            locked={locked}
            onSelect={setSelectedIndex}
            onAdd={addExperiment}
          />

          <NextStepNudge stepKey="experiments" badges={badges} onGo={onGoAssemblyPage} />
        </div>
      )}
    </div>
  );
}

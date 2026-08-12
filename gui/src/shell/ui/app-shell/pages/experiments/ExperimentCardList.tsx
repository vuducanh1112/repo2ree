import { expId } from "@core/ree/experimentRules";
import type { ExperimentResourceEstimates, ReeExperiment } from "@core/ree/ReeSpec";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "./ExperimentsPage.module.css";

function hasResourceEstimates(estimates: ExperimentResourceEstimates): boolean {
  return Object.values(estimates).some((value) => value.trim() !== "");
}

export function ExperimentCardList({
  experiments,
  locked,
  onSelect,
  onAdd,
  onRemove,
}: {
  experiments: ReeExperiment[];
  locked: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  if (experiments.length === 0) {
    return <ExperimentEmptyState locked={locked} onAdd={onAdd} />;
  }
  return (
    <div className={styles.list}>
      {experiments.map((exp, index) => (
        <ExperimentCard
          key={`exp-${String(index)}`}
          experiment={exp}
          index={index}
          locked={locked}
          onSelect={() => onSelect(index)}
          onRemove={() => onRemove(index)}
        />
      ))}
    </div>
  );
}

function ExperimentCard({
  experiment,
  index,
  locked,
  onSelect,
  onRemove,
}: {
  experiment: ReeExperiment;
  index: number;
  locked: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const name = experiment.name.trim();
  const command = experiment.runScript.trim();
  const description = experiment.description.trim();
  const hasVerify = experiment.verifyScript.trim() !== "";
  const runtimeEstimate = experiment.runtimeEstimate.trim();
  const hasResources = hasResourceEstimates(experiment.resourceEstimates);

  return (
    <div className={styles.card}>
      <button type="button" onClick={onSelect} className={styles.open}>
        <div className={styles.cardHead}>
          <span className={styles.expId}>{expId(index)}</span>
          <h3 className={styles.expName} data-untitled={name ? undefined : true}>
            {name || "untitled experiment"}
          </h3>
          {hasVerify && (
            <span className={styles.fact} data-kind="verified">
              verified
            </span>
          )}
          {runtimeEstimate && (
            <span className={styles.fact} data-kind="runtime">
              ~ {runtimeEstimate}
            </span>
          )}
          {hasResources && (
            <span className={styles.fact} data-kind="resources">
              resources
            </span>
          )}
          <span aria-hidden className={styles.cardChevron}>
            {Ic.chevR(15)}
          </span>
        </div>

        <div className={styles.command} data-unset={command ? undefined : true}>
          {command || "no command set"}
        </div>

        {description && <div className={styles.description}>{description}</div>}
      </button>

      {!locked && (
        <div className={styles.cardActions}>
          <Button variant="danger" size="tiny" icon={Ic.x(11)} onClick={onRemove}>
            Delete
          </Button>
        </div>
      )}
    </div>
  );
}

function ExperimentEmptyState({ locked, onAdd }: { locked: boolean; onAdd: () => void }) {
  return (
    <Surface spacing="flush">
      <div className={styles.emptyState}>
        <span aria-hidden className={styles.emptyIcon}>
          {Ic.terminal(28)}
        </span>
        <div className={styles.emptyTitle}>No experiments yet</div>
        <div className={styles.emptyHint}>
          Add a verification command and the assembled REE will be checked against it.
        </div>
        {!locked && (
          <div className={styles.emptyAction}>
            <Button icon={Ic.plus(13)} onClick={onAdd}>
              Add experiment
            </Button>
          </div>
        )}
      </div>
    </Surface>
  );
}

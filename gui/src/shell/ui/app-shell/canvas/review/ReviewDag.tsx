import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import { REVIEW_STEPS, type ReviewStepKey, type ReviewStepStatus } from "@core/reviews/reviewDag";
import { Ic } from "../../../shared/components/Icon";
import { stageTone } from "../../../theme/appearance";
import { C } from "../../../theme/theme";
import { stepIcon } from "../../stepIcons";
import { ReviewStepButton } from "./ReviewStepButton";

const SHARED_STEP_META = Object.fromEntries(REE_STEPS.map((step) => [step.key, step]));

function presentation(key: ReviewStepKey) {
  const shared = SHARED_STEP_META[key];
  if (shared) {
    return {
      label: shared.label.replace(" Runtime", ""),
      color: stageTone(shared.key),
      icon: stepIcon(shared.iconKey)(16),
    };
  }
  if (key === "source") return { label: "Source", color: "#2563eb", icon: Ic.globe(16) };
  return { label: "Experiments", color: "#7c3aed", icon: Ic.terminal(16) };
}

function Connector() {
  return (
    <span
      aria-hidden="true"
      style={{
        width: 18,
        height: 1,
        background: C.borderMid,
        flexShrink: 0,
        marginTop: 33,
      }}
    />
  );
}

export function ReviewDag({
  experimentCount,
  statuses,
  enabledSteps,
  onRunStep,
}: {
  experimentCount: number;
  statuses: Readonly<Partial<Record<ReviewStepKey, ReviewStepStatus>>>;
  enabledSteps: ReadonlySet<ReviewStepKey>;
  onRunStep: (step: ReviewStepKey) => void;
}) {
  const source = REVIEW_STEPS[0];
  const build = REVIEW_STEPS[1];
  const activation = REVIEW_STEPS[2];
  const experiments = REVIEW_STEPS[3];

  const button = (step: (typeof REVIEW_STEPS)[number], detail?: string) => {
    const meta = presentation(step.key);
    return (
      <ReviewStepButton
        stepKey={step.key}
        label={meta.label}
        detail={detail}
        icon={meta.icon}
        color={meta.color}
        status={statuses[step.key] ?? "ready"}
        disabled={!enabledSteps.has(step.key)}
        onRun={onRunStep}
      />
    );
  };

  return (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center" }}>
      {button(source, "SWHID")}
      <Connector />
      {button(build, "runtime · SBOM diff")}
      <Connector />
      {button(activation, "runtime entry")}
      <Connector />
      {button(experiments, `${experimentCount} experiment${experimentCount === 1 ? "" : "s"}`)}
    </div>
  );
}

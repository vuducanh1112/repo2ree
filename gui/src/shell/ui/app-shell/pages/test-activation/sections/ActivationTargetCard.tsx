import { PAGE } from "@core/app-shell/pages";
import { ExperimentEnvironmentTargetCard } from "@shell/ui/app-shell/components/ExperimentEnvironmentTargetCard";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { stageTone } from "@shell/ui/theme/appearance";

interface ActivationTargetCardProps {
  experimentEnvironmentPath: string;
  experimentEnvironmentPathExists: boolean;
  sbomPath: string;
  sbomPathExists: boolean;
}

export function ActivationTargetCard({
  experimentEnvironmentPath,
  experimentEnvironmentPathExists,
  sbomPath,
  sbomPathExists,
}: ActivationTargetCardProps) {
  const experimentEnvironmentReady = !!experimentEnvironmentPath && experimentEnvironmentPathExists;

  return (
    <ExperimentEnvironmentTargetCard
      experimentEnvironmentPath={experimentEnvironmentPath}
      experimentEnvironmentPathExists={experimentEnvironmentPathExists}
      tint={stageTone(PAGE.BUILD_EXPERIMENT_ENVIRONMENT)}
      icon={Ic.archive(20)}
    >
      <Badge tone={experimentEnvironmentReady ? "info" : "neutral"}>
        {experimentEnvironmentReady
          ? "Experiment environment file present"
          : "Experiment environment pending"}
      </Badge>
      <Badge tone={sbomPath && sbomPathExists ? "info" : "neutral"}>
        {sbomPath && sbomPathExists ? "SBOM attached" : "SBOM pending"}
      </Badge>
    </ExperimentEnvironmentTargetCard>
  );
}

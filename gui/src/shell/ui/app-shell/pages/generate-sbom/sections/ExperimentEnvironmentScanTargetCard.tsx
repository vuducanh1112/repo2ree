import { ExperimentEnvironmentTargetCard } from "@shell/ui/app-shell/components/ExperimentEnvironmentTargetCard";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";

interface ExperimentEnvironmentScanTargetCardProps {
  experimentEnvironmentPath: string;
  experimentEnvironmentPathExists: boolean;
  experimentEnvironmentIsTarball: boolean;
  color: string;
}

export function ExperimentEnvironmentScanTargetCard({
  experimentEnvironmentPath,
  experimentEnvironmentPathExists,
  experimentEnvironmentIsTarball,
  color,
}: ExperimentEnvironmentScanTargetCardProps) {
  return (
    <ExperimentEnvironmentTargetCard
      experimentEnvironmentPath={experimentEnvironmentPath}
      experimentEnvironmentPathExists={experimentEnvironmentPathExists}
      tint={color}
      icon={experimentEnvironmentIsTarball ? Ic.archive(20) : Ic.cpu(20)}
    >
      <Badge tone={experimentEnvironmentPath ? "info" : "neutral"}>
        {experimentEnvironmentIsTarball ? "Tarball" : "Experiment environment"}
      </Badge>
    </ExperimentEnvironmentTargetCard>
  );
}

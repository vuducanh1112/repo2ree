import { PAGE } from "@core/app-shell/pages";
import { RuntimeTargetCard } from "@shell/ui/app-shell/components/RuntimeTargetCard";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { stageTone } from "@shell/ui/theme/appearance";

interface ActivationTargetCardProps {
  runtimePath: string;
  runtimePathExists: boolean;
  sbomPath: string;
  sbomPathExists: boolean;
}

export function ActivationTargetCard({
  runtimePath,
  runtimePathExists,
  sbomPath,
  sbomPathExists,
}: ActivationTargetCardProps) {
  const runtimeReady = !!runtimePath && runtimePathExists;

  return (
    <RuntimeTargetCard
      runtimePath={runtimePath}
      runtimePathExists={runtimePathExists}
      tint={stageTone(PAGE.BUILD)}
      icon={Ic.archive(20)}
    >
      <Badge tone={runtimeReady ? "info" : "neutral"}>
        {runtimeReady ? "Runtime file present" : "Runtime pending"}
      </Badge>
      <Badge tone={sbomPath && sbomPathExists ? "info" : "neutral"}>
        {sbomPath && sbomPathExists ? "SBOM attached" : "SBOM pending"}
      </Badge>
    </RuntimeTargetCard>
  );
}

import { RuntimeTargetCard } from "@shell/ui/app-shell/components/RuntimeTargetCard";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";

interface RuntimeScanTargetCardProps {
  runtimePath: string;
  runtimePathExists: boolean;
  runtimeIsTarball: boolean;
  color: string;
}

export function RuntimeScanTargetCard({
  runtimePath,
  runtimePathExists,
  runtimeIsTarball,
  color,
}: RuntimeScanTargetCardProps) {
  return (
    <RuntimeTargetCard
      runtimePath={runtimePath}
      runtimePathExists={runtimePathExists}
      tint={color}
      icon={runtimeIsTarball ? Ic.archive(20) : Ic.cpu(20)}
    >
      <Badge tone={runtimePath ? "info" : "neutral"}>
        {runtimeIsTarball ? "Tarball" : "Runtime"}
      </Badge>
    </RuntimeTargetCard>
  );
}

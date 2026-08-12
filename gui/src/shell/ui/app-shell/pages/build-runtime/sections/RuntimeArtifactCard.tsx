import {
  runtimeArtifactStatus,
  runtimeArtifactStatusLabel,
} from "@core/ree-steps/buildRuntimeUiState";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Notice } from "@shell/ui/shared/components/Notice";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "../BuildRuntimePage.module.css";

interface RuntimeArtifactCardProps {
  runtimePath: string;
  runtimeSize: string | null;
  runtimePathExists: boolean;
  onRuntimeChange: (path: string) => void;
}

/**
 * Declare where the build script writes its runtime. This is authored before
 * the build runs — the build refuses to start without it and fails if nothing
 * lands at the declared path — so it is a free-text declaration, not a picker
 * over files that already exist.
 */
export function RuntimeArtifactCard({
  runtimePath,
  runtimeSize,
  runtimePathExists,
  onRuntimeChange,
}: RuntimeArtifactCardProps) {
  const hasRuntime = !!runtimePath;
  const status = runtimeArtifactStatus({ hasRuntime, runtimePathExists });
  const produced = status === "produced";

  return (
    <Surface spacing="separated">
      <div className={styles.artifactHeader}>
        <div className={styles.artifactIdentity}>
          <span aria-hidden className={styles.artifactIcon}>
            {Ic.archive(15)}
          </span>
          <Caption
            title="Runtime Artifact"
            hint="Where the build script writes the runtime, relative to the workspace. Downstream SBOM and activation read the same path."
          />
        </div>
        <Badge tone={produced ? "success" : "warning"}>{runtimeArtifactStatusLabel(status)}</Badge>
      </div>

      <section aria-label="Runtime artifact">
        <Input
          type="text"
          aria-label="Runtime output path"
          value={runtimePath}
          placeholder="runtime.tar.gz"
          onChange={(event) => onRuntimeChange(event.target.value)}
          flavor="code"
        />
      </section>

      {hasRuntime && (
        <div className={styles.outcome}>
          <Notice tone={produced ? "success" : "info"}>
            <span className={styles.outcomePath} data-produced={produced || undefined}>
              {produced ? Ic.check(13) : Ic.info(13)}
              <code>{produced ? runtimePath : `${runtimePath} — not built yet`}</code>
            </span>
            {runtimeSize && <span className={styles.size}>{runtimeSize}</span>}
          </Notice>
        </div>
      )}
    </Surface>
  );
}

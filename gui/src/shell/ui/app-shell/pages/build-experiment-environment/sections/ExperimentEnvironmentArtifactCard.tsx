import {
  experimentEnvironmentArtifactStatus,
  experimentEnvironmentArtifactStatusLabel,
} from "@core/ree-steps/buildExperimentEnvironmentUiState";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Notice } from "@shell/ui/shared/components/Notice";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "../BuildExperimentEnvironmentPage.module.css";

interface ExperimentEnvironmentArtifactCardProps {
  experimentEnvironmentPath: string;
  experimentEnvironmentSize: string | null;
  experimentEnvironmentPathExists: boolean;
  onExperimentEnvironmentChange: (path: string) => void;
}

/**
 * Declare where the build script writes its runtime. This is authored before
 * the build runs — the build refuses to start without it and fails if nothing
 * lands at the declared path — so it is a free-text declaration, not a picker
 * over files that already exist.
 */
export function ExperimentEnvironmentArtifactCard({
  experimentEnvironmentPath,
  experimentEnvironmentSize,
  experimentEnvironmentPathExists,
  onExperimentEnvironmentChange,
}: ExperimentEnvironmentArtifactCardProps) {
  const hasExperimentEnvironment = !!experimentEnvironmentPath;
  const status = experimentEnvironmentArtifactStatus({
    hasExperimentEnvironment,
    experimentEnvironmentPathExists,
  });
  const produced = status === "produced";

  return (
    <Surface spacing="separated">
      <div className={styles.artifactHeader}>
        <div className={styles.artifactIdentity}>
          <span aria-hidden className={styles.artifactIcon}>
            {Ic.archive(15)}
          </span>
          <Caption
            title="Experiment Environment Artifact"
            hint="Where the build script writes the experiment environment, relative to the workspace. Downstream SBOM and activation read the same path."
          />
        </div>
        <Badge tone={produced ? "success" : "warning"}>
          {experimentEnvironmentArtifactStatusLabel(status)}
        </Badge>
      </div>

      <section aria-label="Experiment environment artifact">
        <Input
          type="text"
          aria-label="Experiment environment output path"
          value={experimentEnvironmentPath}
          placeholder="runtime.tar.gz"
          onChange={(event) => onExperimentEnvironmentChange(event.target.value)}
          flavor="code"
        />
      </section>

      {hasExperimentEnvironment && (
        <div className={styles.outcome}>
          <Notice tone={produced ? "success" : "info"}>
            <span className={styles.outcomePath} data-produced={produced || undefined}>
              {produced ? Ic.check(13) : Ic.info(13)}
              <code>
                {produced
                  ? experimentEnvironmentPath
                  : `${experimentEnvironmentPath} — not built yet`}
              </code>
            </span>
            {experimentEnvironmentSize && (
              <span className={styles.size}>{experimentEnvironmentSize}</span>
            )}
          </Notice>
        </div>
      )}
    </Surface>
  );
}

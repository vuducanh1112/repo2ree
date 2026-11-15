import type { WorkingEnvironment } from "@core/ree/ReeSpec";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "../BuildExperimentEnvironmentPage.module.css";

interface WorkingEnvironmentCardProps {
  workingEnvironment: WorkingEnvironment | null;
  onWorkingEnvironmentChange: (workingEnvironment: WorkingEnvironment | null) => void;
}

/**
 * Declare what every script runs in: an OCI image (pinned by digest, ideally),
 * or the machine that runs each step. The lab runs the scripts there, or
 * refuses with the reason when it cannot.
 */
export function WorkingEnvironmentCard({
  workingEnvironment,
  onWorkingEnvironmentChange,
}: WorkingEnvironmentCardProps) {
  const current = workingEnvironment;
  const change = (oci: string | null) =>
    onWorkingEnvironmentChange(oci === null ? null : { oci, pinned: oci.includes("@sha256:") });

  return (
    <Surface spacing="separated">
      <div className={styles.artifactIdentity}>
        <span aria-hidden className={styles.artifactIcon}>
          {Ic.cpu(15)}
        </span>
        <Caption
          title="Working environment"
          hint="What every script runs in: an OCI image, or the lab's own machine. A reviewer reruns them in the same."
        />
      </div>
      <section aria-label="Working environment">
        <label>
          <input
            type="radio"
            name="working-environment-kind"
            checked={current !== null}
            onChange={() => change(current?.oci ?? "")}
          />{" "}
          An OCI image
        </label>{" "}
        <label>
          <input
            type="radio"
            name="working-environment-kind"
            checked={current === null}
            onChange={() => change(null)}
          />{" "}
          The lab's own machine
        </label>
        {current !== null && (
          <Input
            type="text"
            aria-label="Working environment image"
            value={current.oci}
            placeholder="docker.io/library/python:3.12-slim@sha256:…"
            onChange={(event) => change(event.target.value.trim())}
            flavor="code"
          />
        )}
      </section>
    </Surface>
  );
}

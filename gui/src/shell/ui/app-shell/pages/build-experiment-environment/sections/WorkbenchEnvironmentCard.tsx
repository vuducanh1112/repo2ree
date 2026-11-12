import type { WorkbenchEnvironment } from "@core/ree/ReeSpec";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "../BuildExperimentEnvironmentPage.module.css";

interface WorkbenchEnvironmentCardProps {
  workbenchEnvironment: WorkbenchEnvironment | null;
  onWorkbenchEnvironmentChange: (workbenchEnvironment: WorkbenchEnvironment) => void;
}

const HOST: WorkbenchEnvironment = { oci: null, pinned: false };

/**
 * Declare what the build, and everything run on its runtime, runs in: an OCI
 * image (pinned by digest, ideally), or the lab's own machine. The lab runs the
 * scripts there, or refuses with the reason when it cannot.
 */
export function WorkbenchEnvironmentCard({
  workbenchEnvironment,
  onWorkbenchEnvironmentChange,
}: WorkbenchEnvironmentCardProps) {
  const current = workbenchEnvironment ?? HOST;
  const change = (oci: string | null) =>
    onWorkbenchEnvironmentChange({ oci, pinned: oci?.includes("@sha256:") ?? false });

  return (
    <Surface spacing="separated">
      <div className={styles.artifactIdentity}>
        <span aria-hidden className={styles.artifactIcon}>
          {Ic.cpu(15)}
        </span>
        <Caption
          title="Workbench environment"
          hint="What the scripts run in: an OCI image, or the lab's own machine. A reviewer reruns them in the same."
        />
      </div>
      <section aria-label="Workbench environment">
        <label>
          <input
            type="radio"
            name="workbench-environment-kind"
            checked={current.oci !== null}
            onChange={() => change(current.oci ?? "")}
          />{" "}
          An OCI image
        </label>{" "}
        <label>
          <input
            type="radio"
            name="workbench-environment-kind"
            checked={current.oci === null}
            onChange={() => change(null)}
          />{" "}
          The lab's own machine
        </label>
        {current.oci !== null && (
          <Input
            type="text"
            aria-label="Workbench environment image"
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

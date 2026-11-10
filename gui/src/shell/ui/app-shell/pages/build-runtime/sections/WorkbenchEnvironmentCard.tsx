import type { WorkbenchEnvironment } from "@core/ree/ReeSpec";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import styles from "../BuildRuntimePage.module.css";

interface WorkbenchEnvironmentCardProps {
  workbenchEnvironment: WorkbenchEnvironment | null;
  onWorkbenchEnvironmentChange: (workbenchEnvironment: WorkbenchEnvironment) => void;
}

const HOST: WorkbenchEnvironment = {
  kind: "host",
  image: "",
  pinned: false,
  needsContainerEngine: false,
};

/**
 * Declare what the build, and everything run on its runtime, runs in: a container
 * image (pinned by digest, ideally), or the lab's own machine. The lab runs the
 * scripts there, or refuses with the reason when it cannot.
 */
export function WorkbenchEnvironmentCard({
  workbenchEnvironment,
  onWorkbenchEnvironmentChange,
}: WorkbenchEnvironmentCardProps) {
  const current = workbenchEnvironment ?? HOST;
  const change = (update: Partial<WorkbenchEnvironment>) => {
    const next = { ...current, ...update };
    onWorkbenchEnvironmentChange({
      ...next,
      pinned: next.kind === "image" && next.image.includes("@sha256:"),
    });
  };

  return (
    <Surface spacing="separated">
      <div className={styles.artifactIdentity}>
        <span aria-hidden className={styles.artifactIcon}>
          {Ic.cpu(15)}
        </span>
        <Caption
          title="Workbench environment"
          hint="What the scripts run in: a container image, or the lab's own machine. A reviewer reruns them in the same."
        />
      </div>
      <section aria-label="Workbench environment">
        <label>
          <input
            type="radio"
            name="workbench-environment-kind"
            checked={current.kind === "image"}
            onChange={() => change({ kind: "image" })}
          />{" "}
          A container image
        </label>{" "}
        <label>
          <input
            type="radio"
            name="workbench-environment-kind"
            checked={current.kind === "host"}
            onChange={() => change({ kind: "host", image: "" })}
          />{" "}
          The lab's own machine
        </label>
        {current.kind === "image" && (
          <Input
            type="text"
            aria-label="Workbench environment image"
            value={current.image}
            placeholder="docker.io/library/python:3.12-slim@sha256:…"
            onChange={(event) => change({ image: event.target.value.trim() })}
            flavor="code"
          />
        )}
        <label>
          <input
            type="checkbox"
            checked={current.needsContainerEngine}
            onChange={(event) => change({ needsContainerEngine: event.target.checked })}
          />{" "}
          The scripts call a container engine (docker build, docker run)
        </label>
      </section>
    </Surface>
  );
}

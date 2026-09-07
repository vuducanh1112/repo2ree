import { buildTitle, type DisplayBuildInfo } from "@core/build/buildInfo";
import { useOptionalReeRuntime } from "@shell/data/apiRuntime";
import { useEffect, useState } from "react";
import styles from "./EnvironmentBuild.module.css";

const UNKNOWN_BUILD: DisplayBuildInfo = { version: "", revision: "" };

export function EnvironmentBuild() {
  const runtime = useOptionalReeRuntime();
  const [builds, setBuilds] = useState({ workbench: UNKNOWN_BUILD, executor: UNKNOWN_BUILD });
  useEffect(() => {
    let active = true;
    if (runtime) {
      void runtime.reeApi
        .getReeState(runtime.reeId)
        .then((state) => {
          if (active) {
            setBuilds({
              workbench: state.workbench.build ?? UNKNOWN_BUILD,
              executor: state.workbench.executor_build ?? UNKNOWN_BUILD,
            });
          }
        })
        .catch(() => undefined);
    }
    return () => {
      active = false;
    };
  }, [runtime]);
  const { workbench, executor } = builds;

  return (
    <details className={styles.environment}>
      <summary>Workbench revisions</summary>
      <div className={styles.panel}>
        <div title={buildTitle("Workbench", workbench)}>
          <span>Workbench revision</span>
          <code>{workbench.revision || "development"}</code>
        </div>
        <div title={buildTitle("Executor", executor)}>
          <span>Executor revision</span>
          <code>{executor.revision || "development"}</code>
        </div>
      </div>
    </details>
  );
}

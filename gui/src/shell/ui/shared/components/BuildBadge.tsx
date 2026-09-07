import { buildTitle, type DisplayBuildInfo, revisionLabel } from "@core/build/buildInfo";
import { useOptionalApiServices } from "@shell/data/apiRuntime";
import { useEffect, useState } from "react";
import styles from "./BuildBadge.module.css";

const guiRevision = import.meta.env.VITE_BUILD_REVISION || "development";

export function BuildBadge() {
  const services = useOptionalApiServices();
  const [api, setApi] = useState<DisplayBuildInfo>({});
  useEffect(() => {
    let active = true;
    if (services) {
      void services.reeApi
        .getBuildInfo()
        .then((build) => active && setApi(build))
        .catch(() => undefined);
    }
    return () => {
      active = false;
    };
  }, [services]);

  return (
    <details className={styles.badge}>
      <summary title="Show build revisions">build {revisionLabel(guiRevision)}</summary>
      <div className={styles.panel}>
        <div title={buildTitle("GUI", { revision: guiRevision })}>
          <span>GUI</span>
          <code>{guiRevision}</code>
        </div>
        <div title={buildTitle("API", api)}>
          <span>API</span>
          <code>{api.revision || "development"}</code>
        </div>
      </div>
    </details>
  );
}

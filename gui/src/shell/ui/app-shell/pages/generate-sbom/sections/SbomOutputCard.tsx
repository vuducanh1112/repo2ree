import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Notice } from "@shell/ui/shared/components/Notice";
import { Surface } from "@shell/ui/shared/components/Surface";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "../GenerateSbomPage.module.css";

interface SbomOutputCardProps {
  color: string;
  sbomPath: string;
  sbomFilePresent: boolean;
  pkgCount: number | null;
  sbomFormat: string | null;
}

export function SbomOutputCard({
  color,
  sbomPath,
  sbomFilePresent,
  pkgCount,
  sbomFormat,
}: SbomOutputCardProps) {
  if (!sbomPath) {
    return (
      <Surface spacing="flush">
        <div className={styles.empty}>
          <Badge tone="warning">Not generated</Badge>
          <div className={styles.emptyHint}>
            No SBOM has been attached yet. Generate one from the selected runtime.
          </div>
        </div>
      </Surface>
    );
  }

  if (!sbomFilePresent) {
    return (
      <Notice tone="danger" icon={Ic.info(13)}>
        SBOM is set to <code>{sbomPath}</code>, but that file is not present in the REE.
      </Notice>
    );
  }

  return (
    <div className={styles.attached} style={cssVars({ "--sbom-tint": color })}>
      <span aria-hidden className={styles.attachedIcon}>
        {Ic.file(13)}
      </span>
      <span className={styles.attachedPath}>{sbomPath}</span>
      {sbomFormat && <Badge tone="info">{sbomFormat}</Badge>}
      {pkgCount !== null && (
        <Badge tone="info">
          {pkgCount} package{pkgCount !== 1 ? "s" : ""}
        </Badge>
      )}
    </div>
  );
}

import { Badge } from "@shell/ui/shared/components/Badge";
import { Button } from "@shell/ui/shared/components/Button";
import { Input, Select } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { SegmentedControl } from "@shell/ui/shared/components/SegmentedControl";
import { SourceUploadField } from "../../components/sourceRuntime/SourceUploadField";
import { SourceUrlField } from "../../components/sourceRuntime/SourceUrlField";
import type { SourceAcquisitionPageProps } from "../sharedStepUi";
import styles from "./SourceAcquisitionPage.module.css";
import { SOURCE_TYPE_OPTIONS, type SourceTypeOption } from "./SourceAcquisitionPageHelpers";

interface SourceAcquisitionCardProps {
  repoMode: "url" | "upload";
  sourceConfigLocked: boolean;
  sourceInteractionLocked: boolean;
  sourceInWorkspace: boolean;
  locked: boolean;
  focusedField: string | null;
  originUrlDraft: string;
  originTypeDraft: SourceTypeOption | "";
  revisionDraft: string;
  resolvedRevision: string;
  originInputLocked: boolean;
  priorOriginUrl: string;
  canDownload: boolean;
  canUpload: boolean;
  downloadRunning: boolean;
  downloadDone: boolean;
  downloadLabel: string;
  workspaceSourceState: SourceAcquisitionPageProps["workspaceSourceState"];
  focus: (key: string) => void;
  onRepoModeChange: (mode: "url" | "upload") => void;
  setOriginUrlDraft: (value: string) => void;
  setOriginTypeDraft: (value: SourceTypeOption | "") => void;
  setRevisionDraft: (value: string) => void;
  onDownloadSource: (
    originType: SourceTypeOption | "",
    originUrl: string,
    revision: string,
  ) => void;
  onCancelSource: () => void;
  onWorkspaceUpload: SourceAcquisitionPageProps["onWorkspaceUpload"];
}

export function SourceAcquisitionCard(props: SourceAcquisitionCardProps) {
  return (
    <div>
      <div className={styles.sectionLabel}>Acquisition Method</div>

      <div className={styles.modes}>
        <SegmentedControl
          label="Acquisition method"
          stretch
          value={props.repoMode}
          segments={[
            { key: "url", label: "Use origin URL" },
            { key: "upload", label: "Upload tarball" },
          ]}
          onChange={(mode) => {
            props.focus("sourceAcquiredBy");
            if (props.sourceInteractionLocked || mode === props.repoMode) return;
            props.onRepoModeChange(mode);
            if (mode === "upload") {
              props.setOriginTypeDraft("");
              props.setOriginUrlDraft("");
            }
          }}
        />
      </div>

      {props.sourceConfigLocked && (
        <Badge tone="warning" icon={Ic.lock(11)}>
          Configuration locked — clear workspace source to change method
        </Badge>
      )}

      <div className={styles.methodHint}>
        {props.repoMode === "url"
          ? "Point to an origin and fetch files into this workspace."
          : "Bring a source snapshot directly from a local tarball."}
      </div>

      <div className={styles.snapshot}>
        <div className={styles.sectionLabel}>Source Snapshot</div>

        {props.repoMode === "url" ? (
          <div className={styles.fields}>
            <SourceUrlField
              locked={props.originInputLocked}
              value={props.originUrlDraft}
              priorValue={props.priorOriginUrl}
              onChange={(v) => props.setOriginUrlDraft(v)}
              onFocus={() => props.focus("originUrl")}
            />
            {props.sourceConfigLocked && (
              <div className={styles.hint}>
                Origin URL is locked after source is loaded. Clear workspace source to change.
              </div>
            )}
            {props.originTypeDraft === "git" && (
              <div className={styles.revision}>
                <Input
                  type="text"
                  aria-label="Revision"
                  disabled={props.originInputLocked}
                  value={props.revisionDraft}
                  placeholder="Revision (commit, branch, or tag) — defaults to HEAD"
                  onChange={(e) => props.setRevisionDraft(e.target.value)}
                  onFocus={() => props.focus("revision")}
                />
                {!props.sourceConfigLocked && (
                  <div className={styles.hint}>
                    Leave blank to fetch the default branch's latest commit (HEAD).
                  </div>
                )}
                {props.sourceConfigLocked && props.resolvedRevision && (
                  <div className={styles.hint}>
                    Resolved to commit <code>{props.resolvedRevision}</code> — the exact commit a
                    sealed bundle re-fetches.
                  </div>
                )}
              </div>
            )}
            <div className={styles.acquireRow}>
              <div className={styles.originType}>
                <Select
                  aria-label="Origin type"
                  disabled={props.locked || props.sourceConfigLocked}
                  value={props.originTypeDraft}
                  onChange={(e) =>
                    props.setOriginTypeDraft(e.target.value as SourceTypeOption | "")
                  }
                  onFocus={() => props.focus("sourceType")}
                >
                  <option value="">Select origin type</option>
                  {SOURCE_TYPE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </Select>
              </div>
              <Button
                variant={props.downloadDone ? "secondary" : "primary"}
                size="small"
                busy={props.downloadRunning}
                disabled={props.locked || !props.canDownload || props.downloadRunning}
                icon={props.downloadRunning ? Ic.loader(13) : Ic.download(13)}
                onClick={() =>
                  props.onDownloadSource(
                    props.originTypeDraft,
                    props.originUrlDraft,
                    props.revisionDraft,
                  )
                }
              >
                {props.downloadLabel}
              </Button>
              {props.downloadRunning && (
                <Button
                  variant="danger"
                  size="small"
                  icon={Ic.x(12)}
                  onClick={props.onCancelSource}
                >
                  Cancel
                </Button>
              )}
            </div>
          </div>
        ) : (
          <SourceUploadField
            locked={props.locked}
            disabled={!props.canUpload}
            disabledReason={
              props.sourceInWorkspace
                ? "Source is already loaded. Clear workspace source to switch method."
                : undefined
            }
            committedName={props.workspaceSourceState.uploadedArchive}
            onCommit={(payload) => props.onWorkspaceUpload(payload)}
          />
        )}
      </div>
    </div>
  );
}

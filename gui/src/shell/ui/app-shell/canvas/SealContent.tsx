import { PAGE } from "@core/app-shell/pages";
import { buildSealStepItems } from "@core/canvas/sealSteps";
import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { Badges, LogEntry } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Notice } from "@shell/ui/shared/components/Notice";
import { stageTone } from "@shell/ui/theme/appearance";
import React from "react";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { GlassPageHeader } from "../components/GlassPageHeader";
import { GlassPageShell } from "../components/GlassPageShell";
import { GlassSectionHeader } from "../components/GlassSectionHeader";
import { GlassSubPanel } from "../components/GlassSubPanel";
import { RunActionButton } from "../components/RunActionButton";
import styles from "./SealContent.module.css";
import { SealBundleContents } from "./seal/SealBundleContents";
import { SealedSummary } from "./seal/SealedSummary";

const SEAL_PAGE_COLOR = stageTone(PAGE.SEAL);

interface SealContentProps {
  ree: ReeEditorViewModel;
  badges: Badges;
  locked: boolean;
  sealRunning: boolean;
  sealLog: LogEntry | null;
  onSeal: (inclusionOpts: InclusionOpts) => void;
}

/**
 * The sealing step, built from the same page anatomy as every other authoring
 * step: an identity header carrying the status and the verb, then the page's
 * own sections. It used to be a centred confirmation card — a popup that had
 * been docked — with a bespoke progress bar, warning block, and footer button
 * standing in for the shared header, Notice, and run button.
 */
export function SealContent({
  ree,
  badges,
  locked,
  sealRunning,
  sealLog,
  onSeal,
}: SealContentProps) {
  const sourceAvailable = !!ree.source.sourceAvailable;
  const runtimeAvailable = !!ree.spec.runtime?.trim() && ree.spec.runtime !== "__skipped__";
  // Results are available to seal once any experiment declares an output — those
  // are what a successful run captures into the produced-results store.
  const resultsAvailable = (ree.spec.experiments ?? []).some((e) => e.outputPaths.length > 0);
  const [includeSource, setIncludeSource] = React.useState(sourceAvailable);
  const [includeRuntime, setIncludeRuntime] = React.useState(runtimeAvailable);
  const [includeResults, setIncludeResults] = React.useState(resultsAvailable);

  // Default the seal-time choices to whatever is available; the user can opt out
  // inline before sealing. Availability can change while authoring, so keep the
  // defaults in step with what the workspace actually has.
  React.useEffect(() => {
    setIncludeSource(sourceAvailable);
    setIncludeRuntime(runtimeAvailable);
    setIncludeResults(resultsAvailable);
  }, [sourceAvailable, runtimeAvailable, resultsAvailable]);

  const sealed = locked && !!ree.artifact.sealedAt;
  const stepItems = buildSealStepItems(ree, badges);
  const notDone = stepItems.filter((item) => !item.done);
  const doneCount = stepItems.length - notDone.length;
  const allDone = notDone.length === 0;

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.lock(24)}
        tint={SEAL_PAGE_COLOR}
        title="Seal"
        subtitle="Freeze the REE at the evidence it carries now, and make it read-only."
        badges={
          sealed ? (
            <Badge role="status" aria-label="REE sealed" tone="success" icon={Ic.lock(11)}>
              REE SEALED
            </Badge>
          ) : (
            <Badge tone={allDone ? "success" : "warning"}>
              {doneCount} of {stepItems.length} steps done
            </Badge>
          )
        }
        right={
          sealed ? undefined : (
            <RunActionButton
              label={sealRunning ? "Sealing…" : allDone ? "Seal REE" : "Seal anyway"}
              running={sealRunning}
              disabled={sealRunning}
              idleIcon={Ic.lock}
              variant="accent"
              tint={SEAL_PAGE_COLOR}
              onRun={() =>
                onSeal({
                  includeSource: sourceAvailable && includeSource,
                  includeRuntime: runtimeAvailable && includeRuntime,
                  includeResults: resultsAvailable && includeResults,
                })
              }
            />
          )
        }
      />

      <div className={styles.stack}>
        {sealed ? (
          <GlassSubPanel>
            <GlassSectionHeader
              title="Sealed record"
              subtitle="The REE is frozen and read-only. This digest is what a deposit binds to."
            />
            <SealedSummary ree={ree} />
          </GlassSubPanel>
        ) : (
          <>
            {!allDone && (
              <Notice
                tone="danger"
                icon={Ic.info(13)}
                title={`${notDone.length} step${notDone.length !== 1 ? "s" : ""} not done`}
              >
                <div className={styles.notDone}>
                  {notDone.map((item) => (
                    <span key={item.key} className={styles.notDoneStep}>
                      {item.label}
                    </span>
                  ))}
                </div>
                <div className={styles.notDoneNote}>
                  Sealing now freezes the REE without them — they will not be part of the record.
                </div>
              </Notice>
            )}

            <GlassSubPanel>
              <GlassSectionHeader
                title="Bundle contents"
                subtitle="Choose what the sealed archive carries alongside the REE's evidence."
              />
              <SealBundleContents
                sourceAvailable={sourceAvailable}
                runtimeAvailable={runtimeAvailable}
                resultsAvailable={resultsAvailable}
                includeSource={includeSource}
                includeRuntime={includeRuntime}
                includeResults={includeResults}
                onToggleSource={() => setIncludeSource((v) => !v)}
                onToggleRuntime={() => setIncludeRuntime((v) => !v)}
                onToggleResults={() => setIncludeResults((v) => !v)}
              />
            </GlassSubPanel>
          </>
        )}

        <CollapsibleLogCard log={sealLog} running={sealRunning} title="Seal log" />
      </div>
    </GlassPageShell>
  );
}

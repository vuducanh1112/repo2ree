import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../theme/theme";
import { FieldTipsSidebar } from "../../components/fieldTips";
import { useHardwareBomDraft } from "../../hooks/useHardwareBomDraft";
import type { PageHardwareBomProps } from "../sharedAssemblyUi";
import { HardwareBomHeaderSection } from "./sections/HardwareBomHeaderSection";
import { HardwareBomRunSection } from "./sections/HardwareBomRunSection";
import { HardwareBomTablesSection } from "./sections/HardwareBomTablesSection";

export function PageHardwareBom({
  ree: reeDraft,
  locked,
  badges,
  log,
  running,
  runDone,
  ts,
  focusedField,
  onReeSpecChange,
  onLockedChange,
  onGoAssemblyPage,
  onFocusedFieldChange,
  onRun,
  onCancel,
}: PageHardwareBomProps) {
  const focus = (key: string) => onFocusedFieldChange(key);
  const { draft, updateDraft } = useHardwareBomDraft({ ree: reeDraft, onReeSpecChange });

  useFocusScroll(focusedField);

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <HardwareBomHeaderSection locked={locked} onUnlock={() => onLockedChange(false)} />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <HardwareBomTablesSection
              draft={draft}
              locked={locked}
              focusedField={focusedField}
              onFocusField={focus}
              onDraftChange={updateDraft}
            />

            <HardwareBomRunSection
              running={running}
              runDone={runDone}
              log={log}
              ts={ts}
              badges={badges}
              onCancel={onCancel ? () => onCancel("hbom") : undefined}
              onRun={() => onRun("hbom", {})}
              onGoAssemblyPage={onGoAssemblyPage}
            />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["hardware_description"]}
          focusedField={focusedField}
          onClear={() => onFocusedFieldChange(null)}
        />
      </div>
    </div>
  );
}

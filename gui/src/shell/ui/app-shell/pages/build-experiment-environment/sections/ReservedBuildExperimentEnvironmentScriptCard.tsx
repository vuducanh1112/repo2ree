import type { ScriptTemplateEntry } from "@shell/data/scriptTemplates/catalog";
import {
  RunScriptCard,
  type RunScriptCardProps,
} from "@shell/ui/app-shell/components/RunScriptCard";
import { Ic } from "@shell/ui/shared/components/Icon";

interface ReservedBuildExperimentEnvironmentScriptCardProps {
  currentContent: string;
  disabled?: boolean;
  templates?: ScriptTemplateEntry[];
  externalEdit?: { content: string; nonce: number };
  renderAnalysis?: RunScriptCardProps["renderAnalysis"];
  onSave: (content: string) => void;
}

export function ReservedBuildExperimentEnvironmentScriptCard({
  currentContent,
  disabled = false,
  templates,
  externalEdit,
  renderAnalysis,
  onSave,
}: ReservedBuildExperimentEnvironmentScriptCardProps) {
  return (
    <RunScriptCard
      currentContent={currentContent}
      disabled={disabled}
      templates={templates}
      externalEdit={externalEdit}
      renderAnalysis={renderAnalysis}
      onSave={onSave}
      icon={Ic.file(15)}
      label="Build experiment environment script"
      helper="REE owns this overlay build script. Call project-owned scripts from here when you have them."
      saveButtonContent={<>{Ic.check(13)} Save build script</>}
      savedLabel="Saved as the reserved build script"
      unsavedLabel="Unsaved build script"
    />
  );
}

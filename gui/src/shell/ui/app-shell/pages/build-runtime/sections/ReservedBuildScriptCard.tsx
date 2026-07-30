import type { ScriptTemplateEntry } from "@shell/data/scriptTemplates/catalog";
import { RunScriptCard } from "@shell/ui/app-shell/components/RunScriptCard";
import { Ic } from "@shell/ui/shared/components/Icon";

interface ReservedBuildScriptCardProps {
  currentContent: string;
  disabled?: boolean;
  // Backend-owned build-script template variants; the picker inserts into the
  // editor only, saving stays on the button. The build script itself is seeded
  // at REE creation, so the card's content arrives already prefilled.
  templates?: ScriptTemplateEntry[];
  // A generated candidate to load into the editor (replaces the body, leaves it
  // dirty; the author still saves manually). Bump the nonce on each load.
  externalEdit?: { content: string; nonce: number };
  onSave: (content: string) => void;
}

// The REE-owned build script editor — a thin specialization of RunScriptCard
// that speaks in build terms.
export function ReservedBuildScriptCard({
  currentContent,
  disabled = false,
  templates,
  externalEdit,
  onSave,
}: ReservedBuildScriptCardProps) {
  return (
    <RunScriptCard
      currentContent={currentContent}
      disabled={disabled}
      templates={templates}
      externalEdit={externalEdit}
      onSave={onSave}
      icon={Ic.file(15)}
      label="Build script"
      helper="REE owns this overlay build script. Call project-owned scripts from here when you have them."
      saveButtonContent={<>{Ic.check(13)} Save build script</>}
      savedLabel="Saved as the reserved build script"
      unsavedLabel="Unsaved build script"
    />
  );
}

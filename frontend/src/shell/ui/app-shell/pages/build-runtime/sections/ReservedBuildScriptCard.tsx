import { RunScriptCard } from "@shell/ui/app-shell/components/RunScriptCard";
import { Ic } from "@shell/ui/shared/components/Icon";

interface ReservedBuildScriptCardProps {
  currentContent: string;
  disabled?: boolean;
  onSave: (content: string) => void;
}

// The REE-owned build script editor — a thin specialization of RunScriptCard
// that speaks in build terms. No default template: the build script is seeded
// with the backend-owned starter template at REE creation, so the content the
// card receives is already prefilled.
export function ReservedBuildScriptCard({
  currentContent,
  disabled = false,
  onSave,
}: ReservedBuildScriptCardProps) {
  return (
    <RunScriptCard
      currentContent={currentContent}
      disabled={disabled}
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

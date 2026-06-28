import { RunScriptCard } from "@shell/ui/app-shell/components/RunScriptCard";
import { Ic } from "@shell/ui/shared/components/Icon";

interface ReservedBuildScriptCardProps {
  currentContent: string;
  onSave: (content: string) => void;
}

const DEFAULT_TEMPLATE = `#!/usr/bin/env sh
set -eu

# Build or acquire the runtime artifact and write it to the workspace.
# You can call an existing project script here, for example:
# ./build_runtime.sh

# docker build -t my-runtime:latest .
# docker save my-runtime:latest -o runtime.tar.gz
`;

// The REE-owned build script editor — a thin specialization of RunScriptCard
// that speaks in build terms.
export function ReservedBuildScriptCard({ currentContent, onSave }: ReservedBuildScriptCardProps) {
  return (
    <RunScriptCard
      currentContent={currentContent}
      onSave={onSave}
      icon={Ic.file(15)}
      label="Build script"
      helper="REE owns this overlay build script. Call project-owned scripts from here when you have them."
      defaultTemplate={DEFAULT_TEMPLATE}
      saveButtonContent={<>{Ic.check(13)} Save build script</>}
      savedLabel="Saved as the reserved build script"
      unsavedLabel="Unsaved build script"
    />
  );
}

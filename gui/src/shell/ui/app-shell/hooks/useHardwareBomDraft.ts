import {
  draftFromHBOM,
  type HardwareBomDraft,
  hbomFromDraft,
  hbomSyncKey,
} from "@core/hbom/hardwareBomDraft";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type React from "react";
import { useEffect, useRef, useState } from "react";

interface UseHardwareBomDraftArgs {
  ree: ReeEditorViewModel;
  onReeSpecChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
}

export function useHardwareBomDraft({ ree, onReeSpecChange }: UseHardwareBomDraftArgs) {
  const [draft, setDraft] = useState<HardwareBomDraft>(() =>
    draftFromHBOM(ree.spec.hardwareDescription),
  );
  const pendingLocalHbomKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const incomingKey = hbomSyncKey(ree.spec.hardwareDescription);
    if (pendingLocalHbomKeyRef.current === incomingKey) {
      pendingLocalHbomKeyRef.current = null;
      return;
    }
    setDraft((previous) => draftFromHBOM(ree.spec.hardwareDescription, previous));
  }, [ree.spec.hardwareDescription]);

  const updateDraft = (nextDraft: HardwareBomDraft) => {
    const nextHBOM = hbomFromDraft(nextDraft, ree.spec.hardwareDescription);
    pendingLocalHbomKeyRef.current = hbomSyncKey(nextHBOM);
    setDraft(nextDraft);
    onReeSpecChange((current) => ({
      ...current,
      hardwareDescription: nextHBOM,
    }));
  };

  return {
    draft,
    updateDraft,
  };
}

import type { WorkflowStepCommand } from "../workflow/workflowStepCommands";

export function planSealArtifactCommands(args: {
  sealedAt: string;
  sealHash: string;
}): WorkflowStepCommand[] {
  return [
    {
      type: "patchRee",
      patch: {
        sealedAt: args.sealedAt,
        sealHash: args.sealHash,
      },
    },
    { type: "setLocked", locked: true },
    { type: "toast", message: "REE sealed — now read-only", toastType: "success" },
  ];
}

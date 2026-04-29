import type { ServiceRunCommand } from "./serviceRunCommands";

export function planSealCommands(args: {
  sealedAt: string;
  sealHash: string;
}): ServiceRunCommand[] {
  return [
    {
      type: "patchRee",
      patch: {
        _sealedAt: args.sealedAt,
        _sealHash: args.sealHash,
      },
    },
    { type: "setLocked", locked: true },
    { type: "toast", message: "REE sealed — now read-only", toastType: "success" },
  ];
}

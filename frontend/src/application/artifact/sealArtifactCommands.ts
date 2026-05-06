import type { AssemblyCommand } from "../ree-assembly/assemblyCommands";

export function planSealArtifactCommands(args: {
  sealedAt: string;
  sealHash: string;
}): AssemblyCommand[] {
  return [
    {
      type: "setArtifactStatus",
      artifactStatus: {
        sealedAt: args.sealedAt,
        sealHash: args.sealHash,
      },
    },
    { type: "setLocked", locked: true },
    { type: "toast", message: "REE sealed — now read-only", toastType: "success" },
  ];
}

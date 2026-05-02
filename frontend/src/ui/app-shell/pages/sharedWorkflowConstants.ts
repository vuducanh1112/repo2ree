import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";

export const SVC_SCRIPT_FIELDS: Record<
  string,
  Array<{ label: string; fieldKey: keyof ReeDraftViewModel; scriptKind: "build" | "validate" }>
> = {
  build: [{ label: "Build script", fieldKey: "build_runtime_script", scriptKind: "build" }],
  activation: [
    { label: "Activation script", fieldKey: "activation_script", scriptKind: "validate" },
  ],
};

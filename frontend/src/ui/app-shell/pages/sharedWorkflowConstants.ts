import type { ReeViewState } from "../../../domain/ree/ReeViewState";

export const SVC_SCRIPT_FIELDS: Record<
  string,
  Array<{ label: string; fieldKey: keyof ReeViewState; scriptKind: "build" | "validate" }>
> = {
  build: [{ label: "Build script", fieldKey: "build_runtime_script", scriptKind: "build" }],
  activation: [
    { label: "Activation script", fieldKey: "activation_script", scriptKind: "validate" },
  ],
};

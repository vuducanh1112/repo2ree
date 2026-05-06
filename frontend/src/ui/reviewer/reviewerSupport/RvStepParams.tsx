import type { ReeAssemblyParamValue } from "../../../core/ree-assembly/assemblyStepTypes";
import { C, F, S_SECTION_LABEL } from "../../theme/theme";
import type {
  ReactivationParams,
  ReactivationStep,
  ReactivationStepKey,
} from "./reactivationSteps";

interface RvStepParamsProps {
  step: ReactivationStep;
  params: ReactivationParams;
  onSetParam: (
    stepKey: ReactivationStepKey,
    paramKey: string,
    value: ReeAssemblyParamValue,
  ) => void;
}

export function RvStepParams({ step, params, onSetParam }: RvStepParamsProps) {
  if (!step.params || step.params.length === 0) return null;

  return (
    <div style={{ paddingTop: 12, marginBottom: 12 }}>
      <div
        style={{
          ...S_SECTION_LABEL,
          fontSize: 10,
          marginBottom: 10,
        }}
      >
        Parameters
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {step.params.map((p) => (
          <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: C.text,
                  fontFamily: F.sans,
                }}
              >
                {p.label}
              </div>
              <div style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</div>
            </div>
            {p.type === "bool" ? (
              <button
                type="button"
                onClick={() => onSetParam(step.key, p.key, !params[p.key])}
                style={{
                  width: 40,
                  height: 22,
                  borderRadius: 11,
                  border: "none",
                  cursor: "pointer",
                  background: params[p.key] ? step.color : C.borderMid,
                  position: "relative",
                  flexShrink: 0,
                  transition: "background 0.2s",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 2,
                    left: params[p.key] ? 20 : 2,
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    background: "#fff",
                    transition: "left 0.2s",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }}
                />
              </button>
            ) : p.type === "select" ? (
              <select
                value={String(params[p.key] ?? "")}
                onChange={(event) => onSetParam(step.key, p.key, event.target.value)}
                style={{
                  border: `1.5px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "5px 8px",
                  fontSize: 13,
                  fontFamily: F.mono,
                  color: C.text,
                  background: C.surface,
                  flexShrink: 0,
                }}
              >
                {(p.options ?? []).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

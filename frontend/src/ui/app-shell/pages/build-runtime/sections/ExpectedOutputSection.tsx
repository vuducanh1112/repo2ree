import { Ic } from "../../../../shared/components/Icon";
import {
  C,
  F,
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_SECTION_LABEL_MB12,
} from "../../../../theme/theme";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import type { AssemblyPageProps } from "../../sharedAssemblyUi";

interface ExpectedOutputSectionProps {
  assemblyStep: AssemblyPageProps["assemblyStep"];
  expectedOutput: string;
  setExpectedOutput: (next: string) => void;
  params: AssemblyPageProps["params"];
  setParam: AssemblyPageProps["setParam"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}

export function ExpectedOutputSection({
  assemblyStep,
  expectedOutput,
  setExpectedOutput,
  params,
  setParam,
  focusedField,
  setFocusedField,
}: ExpectedOutputSectionProps) {
  return (
    <FieldSection
      title="Step 2: Expected Output"
      icon={Ic.archive()}
      filledCount={expectedOutput ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="runtime"
        onFocus={() => setFocusedField("runtime")}
        active={focusedField === "runtime"}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <div style={S_FLEX_ROW_CENTER_GAP_6}>
            <span style={S_FIELD_LABEL_TEXT_SM}>Exported runtime file path</span>
            <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
          </div>
          <div style={S_FIELD_HELP_TEXT_SMALL}>
            The filepath where your build script will export the runtime (e.g.,{" "}
            <code style={{ fontFamily: F.mono, fontSize: 10 }}>runtime.tar.gz</code>
            ).
          </div>
          <input
            value={expectedOutput}
            onChange={(event) => setExpectedOutput(event.target.value)}
            onFocus={() => setFocusedField("runtime")}
            placeholder="runtime.tar.gz"
            style={{
              border: `1.5px solid ${expectedOutput ? C.accentBorder : C.border}`,
              borderRadius: 6,
              padding: "5px 8px",
              fontSize: 11,
              fontFamily: F.mono,
              color: C.text,
              background: C.surface,
              width: "100%",
              boxSizing: "border-box",
            }}
          />
        </div>

        {assemblyStep.params && assemblyStep.params.length > 0 && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
            <div style={S_SECTION_LABEL_MB12}>Additional Parameters</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}>
              {assemblyStep.params.map((p) => {
                const paramValue = params[p.key as keyof typeof params];

                return (
                  <div
                    key={p.key}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 5,
                      flex: "0 1 auto",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: C.textMid,
                      }}
                    >
                      {p.label}
                    </div>
                    {p.hint && <div style={S_FIELD_HELP_TEXT_SMALL}>{p.hint}</div>}
                    {p.type === "bool" ? (
                      <button
                        type="button"
                        onClick={() => setParam(p.key, !paramValue)}
                        style={{
                          width: 34,
                          height: 19,
                          borderRadius: 99,
                          border: "none",
                          cursor: "pointer",
                          background: paramValue ? assemblyStep.color : C.borderMid,
                          transition: "background 0.2s",
                          position: "relative",
                        }}
                      >
                        <div
                          style={{
                            position: "absolute",
                            top: 2,
                            left: paramValue ? 17 : 2,
                            width: 15,
                            height: 15,
                            borderRadius: "50%",
                            background: "#fff",
                            transition: "left 0.2s",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.18)",
                          }}
                        />
                      </button>
                    ) : p.type === "select" ? (
                      <select
                        value={String(paramValue ?? "")}
                        onChange={(event) => setParam(p.key, event.target.value)}
                        style={{
                          border: `1.5px solid ${C.border}`,
                          borderRadius: 6,
                          padding: "5px 8px",
                          fontSize: 11,
                          fontFamily: F.mono,
                          color: C.text,
                          background: C.surface,
                        }}
                      >
                        {(p.options ?? []).map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={String(paramValue ?? "")}
                        onChange={(event) => setParam(p.key, event.target.value)}
                        style={{
                          border: `1.5px solid ${C.border}`,
                          borderRadius: 6,
                          padding: "5px 8px",
                          fontSize: 11,
                          fontFamily: F.mono,
                          color: C.text,
                          background: C.surface,
                          boxSizing: "border-box",
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </FieldRow>
    </FieldSection>
  );
}

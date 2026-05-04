import type { ArchiveRepo } from "../../../../../application/workflow/WorkflowStepTypes";
import { C, F, S_SECTION_LABEL } from "../../../../theme/theme";

interface ArchiveParamsCardProps {
  repo: ArchiveRepo;
  getParam: (repoKey: string, paramKey: string) => string | boolean;
  setParam: (repoKey: string, paramKey: string, val: string | boolean) => void;
}

export function ArchiveParamsCard({ repo, getParam, setParam }: ArchiveParamsCardProps) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          padding: "8px 16px",
          background: "#fafbfd",
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            width: 3,
            height: 14,
            borderRadius: 99,
            background: C.borderMid,
            flexShrink: 0,
          }}
        />
        <span style={{ ...S_SECTION_LABEL, letterSpacing: 1 }}>Parameters</span>
      </div>
      <div
        style={{
          padding: "10px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {repo.params.map((p) => (
          <div key={p.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <label
                htmlFor={`repo-${repo.key}-param-${p.key}`}
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: C.textMid,
                  fontFamily: F.sans,
                }}
              >
                {p.label}
              </label>
              <span style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</span>
            </div>
            {p.type === "bool" ? (
              <button
                id={`repo-${repo.key}-param-${p.key}`}
                type="button"
                onClick={() => setParam(repo.key, p.key, !getParam(repo.key, p.key))}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: `1.5px solid ${getParam(repo.key, p.key) ? C.accent : C.border}`,
                  background: getParam(repo.key, p.key) ? C.accentBg : C.bg,
                  cursor: "pointer",
                  width: "fit-content",
                  transition: "all 0.15s",
                }}
              >
                <div
                  style={{
                    width: 30,
                    height: 16,
                    borderRadius: 99,
                    background: getParam(repo.key, p.key) ? C.accent : C.borderMid,
                    position: "relative",
                    transition: "background 0.2s",
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: 2,
                      left: getParam(repo.key, p.key) ? 16 : 2,
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      background: "#fff",
                      transition: "left 0.2s",
                    }}
                  />
                </div>
                <span
                  style={{
                    fontSize: 13,
                    fontFamily: F.sans,
                    color: getParam(repo.key, p.key) ? C.accent : C.textMuted,
                  }}
                >
                  {getParam(repo.key, p.key) ? "yes" : "no"}
                </span>
              </button>
            ) : p.type === "select" ? (
              <select
                id={`repo-${repo.key}-param-${p.key}`}
                value={String(getParam(repo.key, p.key) ?? "")}
                onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                style={{
                  border: `1.5px solid ${C.border}`,
                  borderRadius: 7,
                  padding: "6px 10px",
                  fontSize: 14,
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
                id={`repo-${repo.key}-param-${p.key}`}
                value={String(getParam(repo.key, p.key) ?? "")}
                onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                style={{
                  border: `1.5px solid ${C.border}`,
                  borderRadius: 7,
                  padding: "6px 10px",
                  fontSize: 14,
                  fontFamily: F.mono,
                  color: C.text,
                  background: C.surface,
                }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

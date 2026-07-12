import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { lgColors, lgContentCard, lgInput, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface ArchiveParamsCardProps {
  repo: ArchiveRepo;
  getParam: (repoKey: string, paramKey: string) => string | boolean;
  setParam: (repoKey: string, paramKey: string, val: string | boolean) => void;
}

export function ArchiveParamsCard({ repo, getParam, setParam }: ArchiveParamsCardProps) {
  return (
    <div style={lgContentCard()}>
      <div style={{ ...lgStyles.label, marginBottom: 12 }}>Deposit parameters</div>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {repo.params.map((p) => {
          const inputId = `repo-${repo.key}-param-${p.key}`;
          const value = getParam(repo.key, p.key);
          return (
            <div key={p.key} style={lgStyles.fieldFrame}>
              <label htmlFor={inputId} style={lgStyles.label}>
                {p.label}
                {p.hint && <span style={{ ...lgStyles.helper, fontWeight: 400 }}>{p.hint}</span>}
              </label>

              {p.type === "bool" ? (
                <button
                  id={inputId}
                  type="button"
                  onClick={() => setParam(repo.key, p.key, !value)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 9,
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: `1px solid ${value ? "rgba(14, 165, 233, 0.55)" : "rgba(148, 163, 184, 0.34)"}`,
                    background: value ? "rgba(239, 246, 255, 0.9)" : "rgba(255, 255, 255, 0.6)",
                    cursor: "pointer",
                    width: "fit-content",
                    transition: "all 0.15s",
                  }}
                >
                  <span
                    style={{
                      width: 32,
                      height: 18,
                      borderRadius: 99,
                      background: value ? lgColors.blue : "rgba(148, 163, 184, 0.5)",
                      position: "relative",
                      transition: "background 0.2s",
                      flexShrink: 0,
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: 2,
                        left: value ? 16 : 2,
                        width: 14,
                        height: 14,
                        borderRadius: "50%",
                        background: "#fff",
                        boxShadow: "0 1px 3px rgba(15, 23, 42, 0.3)",
                        transition: "left 0.2s",
                      }}
                    />
                  </span>
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      fontFamily: F.sans,
                      color: value ? lgColors.primaryDeep : lgColors.textMuted,
                    }}
                  >
                    {value ? "Yes" : "No"}
                  </span>
                </button>
              ) : p.type === "select" ? (
                <select
                  id={inputId}
                  value={String(value ?? "")}
                  onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                  style={{ ...lgInput(false), fontFamily: F.mono, cursor: "pointer" }}
                >
                  {(p.options ?? []).map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={inputId}
                  value={String(value ?? "")}
                  onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                  style={{ ...lgInput(false), fontFamily: F.mono }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

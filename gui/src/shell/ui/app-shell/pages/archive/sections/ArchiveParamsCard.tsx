import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { Input, Select } from "@shell/ui/shared/components/FormControl";
import { Surface } from "@shell/ui/shared/components/Surface";
import { Toggle } from "@shell/ui/shared/components/Toggle";
import { archiveTone } from "@shell/ui/theme/appearance";
import styles from "../ArchivePage.module.css";

interface ArchiveParamsCardProps {
  repo: ArchiveRepo;
  getParam: (repoKey: string, paramKey: string) => string | boolean;
  setParam: (repoKey: string, paramKey: string, val: string | boolean) => void;
}

export function ArchiveParamsCard({ repo, getParam, setParam }: ArchiveParamsCardProps) {
  return (
    <Surface>
      <div className={styles.paramsLabel}>Deposit parameters</div>

      <div className={styles.params}>
        {repo.params.map((p) => {
          const inputId = `repo-${repo.key}-param-${p.key}`;
          const value = getParam(repo.key, p.key);
          return (
            <div key={p.key} className={styles.param}>
              <label htmlFor={inputId} className={styles.paramLabel}>
                {p.label}
                {p.hint && <span className={styles.paramHint}>{p.hint}</span>}
              </label>

              {p.type === "bool" ? (
                <Toggle
                  on={!!value}
                  ariaLabel={p.label}
                  tint={archiveTone(repo.key)}
                  title={value ? "Yes" : "No"}
                  onChange={() => setParam(repo.key, p.key, !value)}
                />
              ) : p.type === "select" ? (
                <Select
                  id={inputId}
                  value={String(value ?? "")}
                  onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                >
                  {(p.options ?? []).map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  id={inputId}
                  value={String(value ?? "")}
                  onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                  flavor="code"
                />
              )}
            </div>
          );
        })}
      </div>
    </Surface>
  );
}

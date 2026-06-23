import type { CommandPlan } from "@core/execution/RuntimeCommandPlan";
import type { RuntimeEntry, RuntimeEntryKind } from "@core/ree/ReeSpec";
import { createDefaultRuntimeEntry } from "@core/ree/ReeSpec";
import { CONTAINER_ENGINES, ENGINE_LABELS } from "@core/ree/runtimeEntryLabels";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { lgColors, lgInput } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useEffect, useState } from "react";

interface KindOption {
  kind: RuntimeEntryKind;
  label: string;
  desc: string;
  soon?: boolean;
}

const ENTRY_KINDS: KindOption[] = [
  {
    kind: "container",
    label: "Container",
    desc: "Spin up the runtime image (Docker, Podman, or Apptainer)",
  },
  {
    kind: "local",
    label: "Local / venv",
    desc: "Run directly on the workbench (with optional activate script)",
  },
  { kind: "vm", label: "VM", desc: "Virtual machine substrate", soon: true },
  {
    kind: "custom",
    label: "Custom",
    desc: "Author-supplied phased driver script",
  },
];

// Picks the runtime substrate (`ree.runtime_entry`) — how the workbench enters
// the runtime. Shared by the Runtime environment and Build Runtime pages. The
// accent colour lets each host tint it to its own shell.
//
// `renderDetail` is the slot rendered under the active substrate. By default it
// is the "what actually runs" command plan (relevant on the runtime page). The
// Build Runtime page overrides it to show the build script that substrate uses,
// so the same picker drives "how it's built" there and "how it's entered" here.
export function SubstratePicker({
  entry,
  accent,
  onChange,
  renderDetail,
}: {
  entry: RuntimeEntry;
  accent: string;
  onChange: (next: RuntimeEntry) => void;
  renderDetail?: (entry: RuntimeEntry) => React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {ENTRY_KINDS.map(({ kind, label, desc, soon }) => {
        const active = entry.kind === kind;
        return (
          <div key={kind} style={{ display: "flex", flexDirection: "column" }}>
            <button
              type="button"
              disabled={!!soon}
              onClick={() => {
                // No-op when already selected: re-defaulting would silently wipe
                // fields this compact UI does not expose (workdir/env/gpus, VM
                // SSH config, custom driver path). Engine has its own button row.
                if (soon || active) return;
                onChange(createDefaultRuntimeEntry(kind, entry));
              }}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "10px 12px",
                borderRadius: 8,
                border: `1.5px solid ${active ? accent : "rgba(148, 163, 184, 0.34)"}`,
                background: active ? `${accent}10` : lgColors.white,
                cursor: soon ? "not-allowed" : "pointer",
                opacity: soon ? 0.5 : 1,
                textAlign: "left",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  border: `2px solid ${active ? accent : "rgba(148, 163, 184, 0.5)"}`,
                  background: active ? accent : "transparent",
                  marginTop: 2,
                  flexShrink: 0,
                }}
              />
              <div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: lgColors.text,
                    fontFamily: F.sans,
                  }}
                >
                  {label}
                  {soon && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: 10,
                        color: lgColors.textMid,
                        fontWeight: 400,
                      }}
                    >
                      coming soon
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: lgColors.textMid,
                    fontFamily: F.sans,
                    marginTop: 2,
                  }}
                >
                  {desc}
                </div>
              </div>
            </button>

            {active && entry.kind === "container" && (
              <div style={{ marginTop: 6, paddingLeft: 4 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: lgColors.textMid,
                    fontFamily: F.sans,
                    marginBottom: 4,
                  }}
                >
                  Engine
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {CONTAINER_ENGINES.map((eng) => (
                    <button
                      key={eng}
                      type="button"
                      onClick={() => onChange({ ...entry, engine: eng })}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: `1.5px solid ${entry.engine === eng ? accent : "rgba(148, 163, 184, 0.34)"}`,
                        background: entry.engine === eng ? `${accent}18` : lgColors.white,
                        color: lgColors.text,
                        fontSize: 11,
                        fontFamily: F.sans,
                        cursor: "pointer",
                        fontWeight: entry.engine === eng ? 600 : 400,
                      }}
                    >
                      {ENGINE_LABELS[eng]}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {active &&
              (renderDetail ? (
                renderDetail(entry)
              ) : (
                <DefaultSubstrateDetail entry={entry} onChange={onChange} />
              ))}
          </div>
        );
      })}
    </div>
  );
}

// The default detail slot: how the workbench *enters* the runtime — the editable
// enter-config (local activate / custom driver path) plus the read-only command
// plan. Replaced wholesale by `renderDetail` on the Build Runtime page, which
// cares about how the artifact is *built*, not how it is entered.
function DefaultSubstrateDetail({
  entry,
  onChange,
}: {
  entry: RuntimeEntry;
  onChange: (next: RuntimeEntry) => void;
}) {
  return (
    <>
      {entry.kind === "local" && (
        <div style={{ marginTop: 8 }}>
          <label
            htmlFor="local-activate"
            style={{ fontSize: 11, fontWeight: 600, color: lgColors.textMid, fontFamily: F.sans }}
          >
            Activate script (optional)
          </label>
          <input
            id="local-activate"
            type="text"
            value={entry.activate}
            placeholder="e.g. source .venv/bin/activate"
            onChange={(e) => onChange({ ...entry, activate: e.target.value })}
            style={enterConfigInput}
          />
        </div>
      )}

      {entry.kind === "custom" && (
        <div style={{ marginTop: 8 }}>
          <label
            htmlFor="custom-enter-script"
            style={{ fontSize: 11, fontWeight: 600, color: lgColors.textMid, fontFamily: F.sans }}
          >
            Driver script path
          </label>
          <input
            id="custom-enter-script"
            type="text"
            value={entry.enter_script}
            placeholder="e.g. scripts/my-driver or scripts/my-driver/exec"
            onChange={(e) => onChange({ ...entry, enter_script: e.target.value })}
            style={enterConfigInput}
          />
        </div>
      )}

      <CommandPlanView entry={entry} />
    </>
  );
}

const enterConfigInput: React.CSSProperties = {
  ...lgInput(false),
  marginTop: 4,
  padding: "6px 10px",
  fontSize: 12,
  fontFamily: F.mono,
  minHeight: "unset",
  boxSizing: "border-box",
};

// "What actually runs" — the exact commands the selected substrate executes,
// projected by the backend from the same builders the executors use, so the
// shown commands cannot drift from what runs. Run-scoped values appear as
// placeholder tokens (legend below).
function CommandPlanView({ entry }: { entry: RuntimeEntry }) {
  const { reeApi } = useApiRuntime();
  const [plan, setPlan] = useState<CommandPlan | null>(null);
  const [error, setError] = useState(false);

  // Refetch when the entry changes; debounced so typing the native activate
  // script does not fire a request per keystroke. The entry is small and
  // serialises stably, so its JSON is a sound dependency key.
  const entryKey = JSON.stringify(entry);
  useEffect(() => {
    let alive = true;
    setError(false);
    const handle = setTimeout(() => {
      reeApi
        .getRuntimeCommandPlan(JSON.parse(entryKey) as RuntimeEntry)
        .then((p) => {
          if (alive) setPlan(p);
        })
        .catch(() => {
          if (alive) setError(true);
        });
    }, 250);
    return () => {
      alive = false;
      clearTimeout(handle);
    };
  }, [entryKey, reeApi]);

  if (error) {
    return <div style={noteStyle}>Could not load the command plan.</div>;
  }
  if (!plan) {
    return <div style={noteStyle}>Loading command plan…</div>;
  }
  if (plan.note && plan.phases.length === 0) {
    return <div style={noteStyle}>{plan.note}</div>;
  }

  const placeholderEntries = Object.entries(plan.placeholders);

  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
      {plan.phases
        .filter((phase) => phase.commands.length > 0)
        .map((phase) => (
          <div key={phase.id}>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: 0.4,
                textTransform: "uppercase",
                color: lgColors.textMid,
                fontFamily: F.sans,
                marginBottom: 4,
              }}
            >
              {phase.label}
            </div>
            <pre style={preStyle}>
              {phase.commands
                .map((c) => (c.note ? `${c.display}   # ${c.note}` : c.display))
                .join("\n")}
            </pre>
          </div>
        ))}
      {placeholderEntries.length > 0 && (
        <div style={{ fontSize: 10, color: lgColors.textMid, fontFamily: F.sans, lineHeight: 1.5 }}>
          {placeholderEntries.map(([token, meaning]) => (
            <span key={token} style={{ marginRight: 12 }}>
              <span style={{ fontFamily: F.mono }}>{token}</span> — {meaning}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const preStyle: React.CSSProperties = {
  margin: 0,
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid rgba(148, 163, 184, 0.34)",
  background: "rgba(248, 250, 252, 0.9)",
  color: lgColors.textMid,
  fontSize: 11,
  lineHeight: 1.5,
  fontFamily: F.mono,
  whiteSpace: "pre",
  overflowX: "auto",
};

const noteStyle: React.CSSProperties = {
  marginTop: 8,
  fontSize: 11,
  color: lgColors.textMid,
  fontFamily: F.sans,
};

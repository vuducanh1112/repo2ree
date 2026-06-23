import type { CommandPlan } from "@core/execution/RuntimeCommandPlan";
import type { RuntimeEntry } from "@core/ree/ReeSpec";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { lgColors } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useEffect, useState } from "react";

/** Optional inner command shown above the substrate phases — the thing the
 * substrate wraps and runs (e.g. the activation command written into the run
 * script). The substrate plan only references the run script by placeholder,
 * so callers that know the actual command pass it here to show the full thing. */
interface InnerCommand {
  label: string;
  value: string;
}

// "What actually runs" — the exact commands the selected substrate executes,
// projected by the backend from the same builders the executors use, so the
// shown commands cannot drift from what runs. Run-scoped values appear as
// placeholder tokens (legend below). When `innerCommand` is given it is shown
// first: the substrate `exec` phase only references the run script, so this is
// what makes the preview the full command end-to-end.
export function CommandPlanView({
  entry,
  innerCommand,
}: {
  entry: RuntimeEntry;
  innerCommand?: InnerCommand;
}) {
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

  const innerBlock = innerCommand ? (
    <div>
      <div style={phaseLabelStyle}>{innerCommand.label}</div>
      <pre style={preStyle}>{innerCommand.value}</pre>
    </div>
  ) : null;

  if (error) {
    return (
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
        {innerBlock}
        <div style={noteStyle}>Could not load the command plan.</div>
      </div>
    );
  }
  if (!plan) {
    return (
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
        {innerBlock}
        <div style={noteStyle}>Loading command plan…</div>
      </div>
    );
  }
  if (plan.note && plan.phases.length === 0) {
    return (
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
        {innerBlock}
        <div style={noteStyle}>{plan.note}</div>
      </div>
    );
  }

  const placeholderEntries = Object.entries(plan.placeholders);

  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
      {innerBlock}
      {plan.phases
        .filter((phase) => phase.commands.length > 0)
        .map((phase) => (
          <div key={phase.id}>
            <div style={phaseLabelStyle}>{phase.label}</div>
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

const phaseLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 0.4,
  textTransform: "uppercase",
  color: lgColors.textMid,
  fontFamily: F.sans,
  marginBottom: 4,
};

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

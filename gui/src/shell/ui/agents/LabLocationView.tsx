import type { Agent } from "@core/agent/Agent";
import { type LabPage, selectLabPage } from "@core/agent/labSelection";
import { APP_ROUTE, LOAD_REE_PARAM } from "@core/app-shell/pages";
import { emptyEvaluationState } from "@core/evaluate/EvaluationState";
import { useAgents } from "@shell/data/agents/agents";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { PodWidget } from "../app-shell/canvas/PodWidget";
import { Button } from "../shared/components/Button";
import { Input } from "../shared/components/FormControl";
import { Ic } from "../shared/components/Icon";
import { Notice } from "../shared/components/Notice";
import { agentLoadErrorMessage } from "./agentPresentation";
import { LabGrid } from "./LabGrid";
import styles from "./LabLocationView.module.css";
import { NoAgentsState } from "./NoAgentsState";
import { SelectedLabDetail } from "./SelectedLabDetail";
import { useAgentUptimeClock } from "./useAgentUptimeClock";

interface LabLocationViewProps {
  onBack: () => void;
}

// PodWidget's sphere fills only ~40% of its square viewBox, so the box is much
// larger than the specimen it draws. The bay clips the surplus transparent
// padding rather than the pod.
const POD_SIZE = 460;

// Step 1 of REE creation: choose which agent (lab) will host the workbench.
// Picking one arms it; Continue carries its id into the workbench/image step,
// which pins the REE to that agent on provision. The commit is deliberately two
// moves — the detail panel is where the choice is confirmed, not the grid.
export function LabLocationView({ onBack }: LabLocationViewProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { data: agents, isLoading, isError, error } = useAgents();

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const nowMs = useAgentUptimeClock(Boolean(agents?.length));
  const view = useMemo(() => selectLabPage(agents ?? [], { query, page }), [agents, query, page]);
  const selected = agents?.find((one) => one.id === selectedId) ?? null;

  // One connected lab is not a choice — arm it on arrival so the common
  // single-agent install is one click, not two.
  useEffect(() => {
    if (selectedId || !agents || agents.length !== 1) return;
    setSelectedId(agents[0].id);
  }, [agents, selectedId]);

  // "Load an existing REE" is chosen on the landing screen and asked for on the
  // workbench step, so the intent rides along through this one.
  function commit() {
    if (!selected) return;
    const params = new URLSearchParams({ agentId: selected.id });
    if (searchParams.get(LOAD_REE_PARAM)) params.set(LOAD_REE_PARAM, "1");
    navigate(`${APP_ROUTE.WORKSPACE}?${params.toString()}`);
  }

  return (
    <>
      <main className={styles.bench}>
        <div className={styles.rail}>
          <div className={styles.backRow}>
            <button type="button" onClick={onBack} className={styles.back}>
              {Ic.arrowLeft(15)} Back
            </button>
          </div>

          <div className={styles.heading}>
            <div className={styles.step}>01 · Lab location</div>
            <h1 className={styles.title}>Where should this REE run?</h1>
            <p className={styles.subtitle}>
              repo2ree coordinates the work but doesn't run containers itself. Pick the machine that
              will host this REE's isolated workbench — every build, run, and result happens there.
            </p>
          </div>

          <details className={styles.why}>
            <summary className={styles.whySummary}>
              <span aria-hidden className={styles.whyIcon}>
                {Ic.info(13)}
              </span>
              What is a lab?
            </summary>
            <div className={styles.whyBody}>
              <p>
                This service records what you intend to build. A separately running <b>agent</b>{" "}
                carries that intent to real execution infrastructure and owns Docker on its host.
              </p>
              <p>
                Choosing a lab picks which connected agent does the work. The REE stays with that
                lab for its whole life — its workbench, builds, and runs all live there.
              </p>
            </div>
          </details>

          <div className={styles.podBay}>
            <div className={styles.podFrame}>
              <PodWidget
                evaluation={emptyEvaluationState()}
                size={POD_SIZE}
                idSuffix="lab-picker"
              />
            </div>
          </div>

          <SelectedLabDetail agent={selected} nowMs={nowMs} />
        </div>

        <div className={styles.fleet}>
          {isLoading ? (
            <div role="status">
              <Notice>Loading agents…</Notice>
            </div>
          ) : isError ? (
            <Notice tone="danger">{agentLoadErrorMessage(error)}</Notice>
          ) : !agents || agents.length === 0 ? (
            <NoAgentsState
              standalone
              description="A workbench needs an agent to host it. Start one pointing at this control plane:"
            />
          ) : (
            <FleetBrowser
              agents={agents}
              view={view}
              nowMs={nowMs}
              query={query}
              selectedId={selectedId}
              onQueryChange={(next) => {
                setQuery(next);
                setPage(0);
              }}
              onSelect={setSelectedId}
              onPage={setPage}
            />
          )}
        </div>
      </main>

      <footer className={styles.actionBar}>
        <div className={styles.summary} data-ready={selected ? true : undefined}>
          <span aria-hidden className={styles.summaryLamp} />
          <span className={styles.summaryText}>
            {selected ? (
              <>
                This REE will run on <b>{selected.hostname || selected.id}</b>
              </>
            ) : agents?.length ? (
              "No lab selected"
            ) : (
              "No lab is connected to this control plane."
            )}
          </span>
        </div>
        <Button variant="primary" disabled={!selected} onClick={commit} icon={Ic.chevR(15)}>
          Continue
        </Button>
      </footer>
    </>
  );
}

function FleetBrowser({
  agents,
  view,
  nowMs,
  query,
  selectedId,
  onQueryChange,
  onSelect,
  onPage,
}: {
  agents: Agent[];
  view: LabPage;
  nowMs: number;
  query: string;
  selectedId: string | null;
  onQueryChange: (next: string) => void;
  onSelect: (agentId: string) => void;
  onPage: (page: number) => void;
}) {
  const trimmed = query.trim();
  return (
    <>
      <div className={styles.tools}>
        <Input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Filter labs by name…"
          aria-label="Filter labs"
          density="compact"
        />
        <div className={styles.count}>
          {trimmed
            ? `${view.matches.length} of ${agents.length} labs`
            : `${agents.length} lab${agents.length === 1 ? "" : "s"} connected`}
        </div>
      </div>

      {view.matches.length === 0 ? (
        <Notice>No lab matches “{trimmed}”.</Notice>
      ) : (
        <LabGrid
          agents={view.visible}
          columns={view.columns}
          nowMs={nowMs}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      )}

      {view.pageCount > 1 && (
        <nav className={styles.pager} aria-label="Lab pages">
          <button
            type="button"
            onClick={() => onPage(view.page - 1)}
            disabled={view.page === 0}
            aria-label="Previous page"
            className={styles.pageBack}
          >
            {Ic.chevR(15)}
          </button>
          <span className={styles.pageLabel}>
            page {view.page + 1} / {view.pageCount}
          </span>
          <button
            type="button"
            onClick={() => onPage(view.page + 1)}
            disabled={view.page >= view.pageCount - 1}
            aria-label="Next page"
            className={styles.pageNext}
          >
            {Ic.chevR(15)}
          </button>
        </nav>
      )}
    </>
  );
}

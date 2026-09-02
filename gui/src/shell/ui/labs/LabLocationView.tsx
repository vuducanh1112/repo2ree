import { LOAD_REE_PARAM } from "@core/app-shell/pages";
import { emptyEvaluationState } from "@core/evaluate/EvaluationState";
import type { Lab } from "@core/lab/Lab";
import { type LabPage, selectLabPage } from "@core/lab/labSelection";
import { useLabs } from "@shell/data/labs/labs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { PodWidget } from "../app-shell/canvas/PodWidget";
import { WorkspaceDrawer } from "../app-shell/canvas/WorkspaceDrawer";
import { Input } from "../shared/components/FormControl";
import { Ic } from "../shared/components/Icon";
import { Notice } from "../shared/components/Notice";
import { LabGrid } from "./LabGrid";
import styles from "./LabLocationView.module.css";
import { labLoadErrorMessage } from "./labPresentation";
import { NoLabsState } from "./NoLabsState";
import { SelectedLabDetail } from "./SelectedLabDetail";
import { WorkbenchSetupDrawer } from "./WorkbenchSetupDrawer";

interface LabLocationViewProps {
  onBack: () => void;
}

// PodWidget's sphere fills only ~40% of its square viewBox, so the box is much
// larger than the specimen it draws. The bay clips the surplus transparent
// padding rather than the pod.
const POD_SIZE = 460;

// Step 1 of REE creation: choose which lab will host the workbench.
// Picking one arms it; Continue carries its id into the workbench/image step,
// which pins the REE to that lab on provision. The commit is deliberately two
// moves — the detail panel is where the choice is confirmed, not the grid.
export function LabLocationView({ onBack }: LabLocationViewProps) {
  const [searchParams] = useSearchParams();
  const { data: labs, isLoading, isError, error } = useLabs();

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Choosing a lab opens the setup drawer over the grid, the same way a canvas
  // panel opens its authoring page. Closing it leaves the choice standing.
  const [setupOpen, setSetupOpen] = useState(false);
  // Arrived from "Load existing REE" on the landing screen: the bundle is asked
  // for in the drawer, because the load runs on the bench it provisions.
  const loadRequested = Boolean(searchParams.get(LOAD_REE_PARAM));

  const view = useMemo(() => selectLabPage(labs ?? [], { query, page }), [labs, query, page]);
  const selected = labs?.find((one) => one.id === selectedId) ?? null;

  // One connected lab is not a choice — arm it on arrival so the common
  // single-lab install is one click, not two.
  useEffect(() => {
    if (selectedId || !labs || labs.length !== 1) return;
    setSelectedId(labs[0].id);
  }, [labs, selectedId]);

  function chooseLab(labId: string) {
    setSelectedId(labId);
    setSetupOpen(true);
  }

  return (
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
              This service records what you intend to build. A separately running <b>lab</b> carries
              that intent to real execution infrastructure and owns Docker on its host.
            </p>
            <p>
              Choosing a lab picks which connected lab does the work. The REE stays with that lab
              for its whole life — its workbench, builds, and runs all live there.
            </p>
          </div>
        </details>

        <div className={styles.podBay}>
          <div className={styles.podFrame}>
            <PodWidget evaluation={emptyEvaluationState()} size={POD_SIZE} idSuffix="lab-picker" />
          </div>
        </div>

        <SelectedLabDetail lab={selected} />
      </div>

      <div className={styles.fleet}>
        {isLoading ? (
          <div role="status">
            <Notice>Loading labs…</Notice>
          </div>
        ) : isError ? (
          <Notice tone="danger">{labLoadErrorMessage(error)}</Notice>
        ) : !labs || labs.length === 0 ? (
          <NoLabsState
            standalone
            description="No lab is connected. Start a workbench service pointing at this control plane:"
          />
        ) : (
          <FleetBrowser
            labs={labs}
            view={view}
            query={query}
            selectedId={selectedId}
            onQueryChange={(next) => {
              setQuery(next);
              setPage(0);
            }}
            onSelect={chooseLab}
            onPage={setPage}
          />
        )}
      </div>

      {setupOpen && selected && (
        <WorkspaceDrawer
          node={undefined}
          title="Set up the workbench"
          subtitle="Setup"
          icon={Ic.package(13)}
          onClose={() => setSetupOpen(false)}
        >
          <WorkbenchSetupDrawer lab={selected} loadRequested={loadRequested} />
        </WorkspaceDrawer>
      )}
    </main>
  );
}

function FleetBrowser({
  labs,
  view,
  query,
  selectedId,
  onQueryChange,
  onSelect,
  onPage,
}: {
  labs: Lab[];
  view: LabPage;
  query: string;
  selectedId: string | null;
  onQueryChange: (next: string) => void;
  onSelect: (labId: string) => void;
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
            ? `${view.matches.length} of ${labs.length} labs`
            : `${labs.length} lab${labs.length === 1 ? "" : "s"} connected`}
        </div>
      </div>

      {view.matches.length === 0 ? (
        <Notice>No lab matches “{trimmed}”.</Notice>
      ) : (
        <LabGrid
          labs={view.visible}
          columns={view.columns}
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

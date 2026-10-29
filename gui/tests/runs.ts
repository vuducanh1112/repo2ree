import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { type Page, type Response, test } from "@playwright/test";
import type { components } from "../src/shell/infra/api/generated/openapi";

/**
 * How long a run may go without a new log line before it counts as stalled,
 * and the overall backstop. A run that keeps logging is never failed for being
 * slow; one that goes quiet fails with what it said last.
 */
export interface RunWatch {
  stallMs: number;
  budgetMs: number;
}

/** Runs that download nothing and start no daemon: the instant fixture. */
const INSTANT_RUN: RunWatch = { stallMs: 30_000, budgetMs: 180_000 };

/** Runs that provision a bench, fetch a source, or pull and build on a cold daemon. */
export const NETWORK_RUN: RunWatch = { stallMs: 120_000, budgetMs: 1_200_000 };

/** The watch the running project names in its `metadata.runWatch`; network runs unless it says `instant`. */
function projectRunWatch(): RunWatch {
  return test.info().project.metadata?.runWatch === "instant" ? INSTANT_RUN : NETWORK_RUN;
}

/** For a step whose tool prints nothing while it works, an SBOM scan above all: five minutes of silence. */
export function quiet(watch: RunWatch = projectRunWatch()): RunWatch {
  return { ...watch, stallMs: Math.max(watch.stallMs, 300_000) };
}

interface StartedRun {
  apiBase: string;
  reeId: string;
  runId: string;
}

type RunSummary = components["schemas"]["RunSummary"];
type RunLogPage = components["schemas"]["RunLogPage"];

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
const POLL_MS = 500;
const TAIL_LINES = 20;

async function runStartedBy(response: Response): Promise<StartedRun | null> {
  if (response.request().method() !== "POST" || !response.ok()) return null;
  const url = response.url();
  if (!new URL(url).pathname.startsWith("/api/v1/rees")) return null;
  const body = (await response.json().catch(() => null)) as Partial<RunSummary> | null;
  if (!body || typeof body.run_id !== "string" || typeof body.ree_id !== "string") return null;
  return { apiBase: url.slice(0, url.indexOf("/api/v1/")), reeId: body.ree_id, runId: body.run_id };
}

/**
 * Every run the page starts from now on, in order. For actions that start more
 * than one run, or start a run only after another one ends: provisioning a
 * workbench with a bundle loads the bundle once provisioning succeeds.
 */
export class StartedRuns {
  private readonly started: StartedRun[] = [];
  private readonly waiting: ((run: StartedRun) => void)[] = [];
  private readonly listener = (response: Response) => {
    void runStartedBy(response).then((run) => {
      if (run === null) return;
      const waiter = this.waiting.shift();
      if (waiter) waiter(run);
      else this.started.push(run);
    });
  };

  constructor(private readonly page: Page) {
    page.on("response", this.listener);
  }

  /** The next run the page started, waiting up to `timeoutMs` for it to start. */
  async next(timeoutMs: number = projectRunWatch().stallMs): Promise<StartedRun> {
    const ready = this.started.shift();
    if (ready) return ready;
    return new Promise<StartedRun>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiting.splice(this.waiting.indexOf(waiter), 1);
        reject(new Error(`no run started within ${Math.round(timeoutMs / 1000)}s`));
      }, timeoutMs);
      const waiter = (run: StartedRun) => {
        clearTimeout(timer);
        resolve(run);
      };
      this.waiting.push(waiter);
    });
  }

  stop() {
    this.page.off("response", this.listener);
  }
}

/** One line per settled run in the test's output, which is what a stall window is tuned against. */
function recordRun(record: Record<string, string | number>) {
  const info = test.info();
  info.annotations.push({ type: "run", description: JSON.stringify(record) });
  mkdirSync(info.outputDir, { recursive: true });
  appendFileSync(path.join(info.outputDir, "runs.ndjson"), `${JSON.stringify(record)}\n`);
}

export interface SettleOptions {
  watch?: RunWatch;
  /** Fail, with the run's failure and last log lines, unless it succeeded. */
  succeed?: boolean;
}

/**
 * Wait until `run` settles and return it. Fails when the run logs nothing for
 * the watch's stall window or is still going past its budget, with the run's
 * last log lines in the error.
 */
export async function settleRun(
  page: Page,
  run: StartedRun,
  { watch = projectRunWatch(), succeed = false }: SettleOptions = {},
): Promise<RunSummary> {
  const base = `${run.apiBase}/api/v1/rees/${run.reeId}/runs/${run.runId}`;
  const started = Date.now();
  let lastProgress = started;
  let longestSilence = 0;
  let status = "";
  let cursor: string | null = null;
  const tail: string[] = [];

  const failure = (reason: string) =>
    new Error(
      `run ${run.runId} ${reason}; last log lines:\n${tail.length ? tail.join("\n") : "(none)"}`,
    );

  for (;;) {
    const now = Date.now();
    const summary = (await (await page.request.get(base)).json()) as RunSummary;
    const logs = (await (
      await page.request.get(`${base}/logs`, cursor === null ? {} : { params: { cursor } })
    ).json()) as RunLogPage;
    if (logs.entries.length || summary.status !== status) {
      longestSilence = Math.max(longestSilence, now - lastProgress);
      lastProgress = now;
    }
    for (const entry of logs.entries) {
      tail.push(`[${entry.level}] ${entry.message}`);
      if (tail.length > TAIL_LINES) tail.shift();
    }
    cursor = logs.next_cursor ?? cursor;
    status = summary.status;

    if (TERMINAL.has(status)) {
      recordRun({
        operation: summary.operation,
        status,
        seconds: Math.round((now - started) / 1000),
        longestSilenceSeconds: Math.round(longestSilence / 1000),
        stallSeconds: Math.round(watch.stallMs / 1000),
      });
      if (succeed && status !== "succeeded") {
        throw failure(
          `${summary.operation} ${status}: ${summary.failure?.message ?? "no failure recorded"}`,
        );
      }
      return summary;
    }
    if (now - lastProgress > watch.stallMs) {
      throw failure(
        `${summary.operation} logged nothing for ${Math.round(watch.stallMs / 1000)}s while ${status}`,
      );
    }
    if (now - started > watch.budgetMs) {
      throw failure(
        `${summary.operation} still ${status} after ${Math.round(watch.budgetMs / 1000)}s`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}

/** Perform `action` and return the run it started, to be settled later with {@link settleRun}. */
export async function startRun(page: Page, action: () => Promise<unknown>): Promise<StartedRun> {
  const runs = new StartedRuns(page);
  try {
    await action();
    return await runs.next();
  } finally {
    runs.stop();
  }
}

/** Perform `action` and wait for the run it started to settle. */
export async function runToEnd(
  page: Page,
  action: () => Promise<unknown>,
  options: SettleOptions = {},
): Promise<RunSummary> {
  return settleRun(page, await startRun(page, action), options);
}

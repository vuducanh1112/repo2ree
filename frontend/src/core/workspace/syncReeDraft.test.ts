import { describe, expect, it } from "vitest";
import { shouldHydrateRemoteRee, shouldScheduleReeDraftSync } from "./syncReeDraft";

describe("syncReeDraft planning", () => {
  it("avoids hydrating when local sync is pending", () => {
    expect(
      shouldHydrateRemoteRee({
        forceReeHydration: false,
        hasHydratedRemoteRee: true,
        latestLocalPatchKey: "local",
        lastSyncedPatchKey: "remote",
        hasSyncTimer: false,
        isSyncingRee: false,
      }),
    ).toBe(false);
  });

  it("does not hydrate the first remote draft over pending local changes", () => {
    expect(
      shouldHydrateRemoteRee({
        forceReeHydration: false,
        hasHydratedRemoteRee: false,
        latestLocalPatchKey: "local",
        lastSyncedPatchKey: "remote",
        hasSyncTimer: false,
        isSyncingRee: false,
      }),
    ).toBe(false);
  });

  it("allows explicit force hydration when no local changes occurred during the request", () => {
    expect(
      shouldHydrateRemoteRee({
        forceReeHydration: true,
        hasHydratedRemoteRee: false,
        latestLocalPatchKey: "remote",
        lastSyncedPatchKey: "remote",
        hasSyncTimer: false,
        isSyncingRee: false,
      }),
    ).toBe(true);
  });

  it("does not force hydrate over pending local changes", () => {
    expect(
      shouldHydrateRemoteRee({
        forceReeHydration: true,
        hasHydratedRemoteRee: true,
        latestLocalPatchKey: "local",
        lastSyncedPatchKey: "remote",
        hasSyncTimer: false,
        isSyncingRee: false,
      }),
    ).toBe(false);
  });

  it("hydrates when there is no pending local sync", () => {
    expect(
      shouldHydrateRemoteRee({
        forceReeHydration: false,
        hasHydratedRemoteRee: true,
        latestLocalPatchKey: "same",
        lastSyncedPatchKey: "same",
        hasSyncTimer: false,
        isSyncingRee: false,
      }),
    ).toBe(true);
  });

  it("only schedules remote draft sync when remote draft updates are available and dirty", () => {
    expect(
      shouldScheduleReeDraftSync({
        canUpdateReeDraft: true,
        patchKey: "local",
        lastSyncedPatchKey: "remote",
      }),
    ).toBe(true);

    expect(
      shouldScheduleReeDraftSync({
        canUpdateReeDraft: false,
        patchKey: "local",
        lastSyncedPatchKey: "remote",
      }),
    ).toBe(false);
  });
});

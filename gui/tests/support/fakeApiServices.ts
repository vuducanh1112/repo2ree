import type { ApiServicesValue } from "@shell/data/apiRuntime";
import type { ReeState } from "@shell/infra/api/apiTypes";
import type { ReeApi } from "@shell/infra/api/ReeApi";
import type { ReeRunsApi } from "@shell/infra/api/ReeRunsApi";

type Overrides<T extends object> = Partial<{ [K in keyof T]: T[K] }>;

function rejectingFake<T extends object>(label: string, overrides: Overrides<T>): T {
  return new Proxy(overrides as T, {
    get(target, property, receiver) {
      if (Reflect.has(target, property)) return Reflect.get(target, property, receiver);
      if (typeof property === "symbol") return Reflect.get(target, property, receiver);
      throw new Error(`Unexpected ${label} access: ${property}`);
    },
  });
}

export function fakeApiServices({
  ree = {},
  runs = {},
}: {
  ree?: Overrides<ReeApi>;
  runs?: Overrides<ReeRunsApi>;
} = {}): ApiServicesValue {
  const reeDefaults: Overrides<ReeApi> = {
    getBuildInfo: async () => ({ version: "0.1.0", revision: "test-gui-api" }),
    getReeState: async () =>
      ({
        workbench: {
          status: "available",
          build: { version: "0.1.0", revision: "test-workbench" },
          // biome-ignore lint/complexity/useLiteralKeys: computed form avoids applying domain naming rules to a wire key
          ["executor_build"]: { version: "0.1.0", revision: "test-executor" },
        },
      }) as ReeState,
    ...ree,
  };
  return {
    reeApi: rejectingFake<ReeApi>("ReeApi", reeDefaults),
    runsApi: rejectingFake<ReeRunsApi>("ReeRunsApi", runs),
  };
}

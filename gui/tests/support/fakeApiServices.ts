import type { ApiServicesValue } from "@shell/data/apiRuntime";
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
  return {
    reeApi: rejectingFake<ReeApi>("ReeApi", ree),
    runsApi: rejectingFake<ReeRunsApi>("ReeRunsApi", runs),
  };
}

import { asReeId, type ReeId } from "../../core/ree/ReeId";
import type { ApiRuntimeValue } from "./apiRuntime";

export function resolveReeId(runtime: ApiRuntimeValue, reeId?: ReeId | string): ReeId {
  return asReeId(reeId || runtime.reeId);
}

export async function ensureReeId(
  runtime: ApiRuntimeValue,
  reeId?: ReeId | string,
): Promise<ReeId> {
  return runtime.ensureReeId(resolveReeId(runtime, reeId));
}

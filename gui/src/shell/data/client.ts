import { asReeId, DEFAULT_REE_ID, type ReeId } from "../../core/ree/ReeId";
import type { ReeRuntimeValue } from "./apiRuntime";

export function resolveReeId(runtime: ReeRuntimeValue, reeId?: ReeId | string): ReeId {
  return asReeId(reeId || runtime.reeId);
}

export function requireReeId(runtime: ReeRuntimeValue, reeId?: ReeId | string): ReeId {
  const resolved = resolveReeId(runtime, reeId);
  if (resolved === DEFAULT_REE_ID) {
    throw new Error("A provisioned REE is required for this operation");
  }
  return resolved;
}

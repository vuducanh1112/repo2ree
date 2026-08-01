import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDocument } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDocument) {
  return mapRawReeIntentToSlices({
    reeIntent: ree.ree_intent,
    reeSession: ree.ree_state,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.external_ref ?? "",
  });
}

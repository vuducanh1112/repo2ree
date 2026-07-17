import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDetailDto } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDetailDto) {
  return mapRawReeIntentToSlices({
    reeIntent: ree.ree_intent,
    reeSession: ree.ree_session,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.external_ref ?? "",
  });
}

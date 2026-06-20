import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDetailDto } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDetailDto) {
  return mapRawReeIntentToSlices({
    reeIntent: ree.reeIntent,
    reeSession: ree.reeSession,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.externalRef ?? "",
  });
}

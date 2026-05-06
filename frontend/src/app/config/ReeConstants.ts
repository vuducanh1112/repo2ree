import { asReeId, type ReeId } from "../../core/ree/ReeId";

// The default REE id used when the URL does not specify one. Each REE has
// exactly one workspace; this id refers to the REE.
export const DEFAULT_REE_ID: ReeId = asReeId("active");

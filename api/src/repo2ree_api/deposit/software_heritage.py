"""Software Heritage — the odd one out, and the only one useful without credentials.

SWH archives *source code reached by URL*, not deposited bytes. So it splits
cleanly in two:

* **Presence lookup** (implemented seam, no credentials): ``POST /api/1/known/``
  answers whether a SWHID is already in the archive. This is the piece worth
  having — it turns "we computed a SWHID" into "this source is independently
  preserved", which is a genuine reproducibility signal and the only honest
  basis for an "archived at Software Heritage" badge.
* **Deposit** (blocked, not unimplemented): getting bytes *into* SWH needs the
  SWORD deposit API, whose credentials SWH grants per organisation rather than
  self-service. Save Code Now is not a substitute — it takes a public VCS origin
  URL, so it can do nothing for an uploaded tarball, which has no URL at all.

Two caveats worth keeping in view when the lookup is wired up:

* A ``known`` hit means the *object* exists, not that it is citable. A citation
  wants the qualified form (``…;origin=…;visit=…;anchor=…``), which is a second
  lookup.
* For a git source, ``swh:1:rev:<HEAD>`` is the more reliable key than the
  directory SWHID: the directory hash skews whenever the working tree differs
  from the committed tree, which an upload or a wrapper directory guarantees.
"""

from __future__ import annotations

from repo2ree_api.deposit.adapter import DepositNotSupportedError
from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)

# The public archive API. Anonymous callers are rate limited rather than
# refused, so the lookup needs no account — only politeness.
SWH_API_ROOT = "https://archive.softwareheritage.org/api/1"

# ``/known/`` takes a batch of SWHIDs and answers each. Batching is what keeps
# the lookup inside the anonymous rate limit.
SWH_KNOWN_ENDPOINT = f"{SWH_API_ROOT}/known/"
SWH_KNOWN_BATCH_LIMIT = 1000


class SoftwareHeritageAdapter:
    """Presence lookups against the public archive; deposit is credential-gated."""

    archive = "software_heritage"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="software_heritage",
            supports_presence_lookup=True,
            supports_bundle_deposit=False,
            requires_origin_url=True,
            requires_institutional_credentials=True,
            supports_identifier_prereservation=False,
            notes=(
                "Archives source reached by URL, not uploaded bytes. Presence lookup is "
                "open; deposit needs SWORD credentials granted per organisation."
            ),
        )

    def check_presence(self, subject: str) -> ArchivePresenceObservation:
        """Whether ``subject`` (a SWHID) is already in the archive.

        Cache the answer keyed by the SWHID itself: it is content-addressed, so
        it is the same answer for every REE and every user. The two directions
        are not symmetric — an archive is monotonic, so a ``known`` result is
        permanent and can be cached forever, while ``unknown`` needs a TTL. That
        asymmetry is what lets a badge appear later without anyone re-asking,
        and what keeps the anonymous rate limit survivable.
        """
        raise NotImplementedError("SWH presence lookup not wired up yet")

    def create_draft(self, request: DepositRequest) -> DepositRecord:
        raise DepositNotSupportedError(
            "Software Heritage does not accept uploaded bundles; its deposit API requires "
            "institutional SWORD credentials"
        )

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        raise DepositNotSupportedError(
            "Software Heritage does not accept uploaded bundles; its deposit API requires "
            "institutional SWORD credentials"
        )

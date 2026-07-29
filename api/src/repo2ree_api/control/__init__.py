"""The control plane: REE lifecycle, background runs, and the agent fleet.

Everything here exists for every REE regardless of where it stands in the
authoring step graph. The step graph itself lives in
:mod:`repo2ree_api.authoring` (author side) and :mod:`repo2ree_api.review`
(reviewer side).

Every collection here is a *liveness projection*: it is derived from current
infrastructure and drops entries as that infrastructure goes away. What must
outlive the infrastructure lives in the siblings — :mod:`repo2ree_api.deposit`
(placing a sealed REE into an archive) and :mod:`repo2ree_api.ree_index` (the
durable record of what was sealed and where it was deposited).
"""

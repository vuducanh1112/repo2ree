"""The control plane: REE lifecycle, background runs, and the agent fleet.

Everything here exists for every REE regardless of where it stands in the
authoring step graph. The step graph itself lives in
:mod:`repo2ree_api.authoring` (author side) and :mod:`repo2ree_api.review`
(reviewer side).
"""

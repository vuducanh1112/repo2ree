"""The reviewer's side of the REE step graph.

A review attempt independently reproduces an author's REE through the
reviewer-facing lifecycle — source, build, activation, experiments
(``repo2ree_core.evidence.review.models.ReviewStepKey``) — in its own namespace, where it can
never write to author evidence. :mod:`stages` mirrors
:mod:`repo2ree_api.authoring.stages` one step at a time; :mod:`records` reads the
attempts back.
"""

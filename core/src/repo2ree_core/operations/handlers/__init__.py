"""One module per command, split by which lifecycle the command belongs to.

:mod:`.author` builds an REE; :mod:`.review` reproduces one in a parallel tree.
They deliberately look alike — a review step mirrors the author step it
certifies — which is exactly what makes a shortcut between them tempting and
wrong: a reviewer handler reaching into an authoring handler would let review
evidence be produced by the code under review. Both compose
:mod:`repo2ree_core.operations.steps` instead, and an import-linter contract
holds the two apart.

Modules are named for their command, so the package supplies the half of the
name the lifecycle already says: ``handlers.review.build_runtime`` is the
reviewer's build, ``handlers.author.build_runtime`` the author's.
"""

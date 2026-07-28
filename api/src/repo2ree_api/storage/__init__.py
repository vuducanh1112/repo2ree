"""The API's only host-side persistence: the upload staging area.

``upload_staging`` owns the transient dir that HTTP uploads land in before they
are ``docker cp``'d into a workbench; ``init_storage`` creates it at startup.
Everything else the API touches lives inside an REE, which is why this is the
one tier below :mod:`repo2ree_api.workbench` rather than beside it.

This package exists as a package — rather than a bare directory — so the import
graph can see it. Without ``__init__.py`` it was an implicit namespace package,
invisible to grimp, and the ``API layers`` contract silently did not constrain
the three tiers that import it.
"""

"""What an REE's recipe should say, before an author has written it.

The recipe is the author's own shell — the build, activation, and experiment
scripts that live in ``overlay/`` and say how this particular work is built and
run. repo2ree never authors them; it proposes them, two ways:

    templates   hand-written starters, offered as a catalog to pick from
    inference   proposals derived from the repository's own evidence

Both answer one question, which is why they are siblings rather than strangers
three directories apart: given this repository, what should this script say?
Neither decides — the author edits whatever lands in the overlay, and the REE
records only what is there.

Distinct from ``reproduction``, which generates the REE's *own* scripts: those
are machinery no author touches, and they are the same in every REE.
"""

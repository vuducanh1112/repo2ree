"""Evidence produced by authoring and review, and the readings derived from it.

Everything here is *about* a stored REE without being its persistence boundary:
it depends on ``persistence`` to read the REE directory and nothing depends on
it except the layers that compose — ``bundle``, which publishes evidence into
the archive, and ``operations``, which serves it.

    review/     a reviewer's independent re-execution and its comparisons
"""

"""Evidence produced by authoring and review, and the readings derived from it.

Everything here is *about* a stored REE without being its persistence boundary:
it depends on ``persistence`` to read the REE directory and nothing depends on
it except the layers that compose — ``bundle``, which publishes evidence into
the archive, and ``operations``, which serves it.

    consistency what recorded receipts still mean against the current tree
    review/     a reviewer's independent re-execution and its comparisons
    scorecard   the reproducibility rung the evidence supports
    step_graph  done / ready / blocked, per authoring step

``step_graph`` rather than ``steps``: ``operations.steps`` is the machinery a
handler is built out of, and this is the checklist a client navigates by. The
two share a word and nothing else, which is exactly the pair worth keeping
un-alike in an import line.
"""

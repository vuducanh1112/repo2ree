"""The vocabulary graph: every closed set of names the repository spells, and how each is held to another.

A vocabulary is a set of names read fresh from where it lives: a table of the specification's
catalogue, a schema's enum or properties in a generated contract, or a literal in source. An edge
says how a vocabulary stands to others: it ``equals`` their union, lies ``within`` it, or is
``derived`` from it (generated, so it cannot drift and is not checked). Edges may name extras, the
names a vocabulary has of its own; each extra must be used. The roots are the catalogue's tables.

``check`` evaluates every edge, requires the copies of a contract vocabulary to agree, requires
every vocabulary to reach a root, and discovers every set of names that shares one with the
catalogue: in the contracts, in Python source, and in the GUI. Each must be claimed by a
vocabulary, by a known gap (a hand-written set nothing holds yet, with its reason), or as no
vocabulary (with its reason); a claim that matches nothing is stale.

    python -m scripts.vocabulary check            # exit 1 on any problem; lists the known gaps
    python -m scripts.vocabulary graph            # the graph as Mermaid
    python -m scripts.vocabulary export           # the graph and what the check found, as JSON for the overview
    python -m scripts.vocabulary impact NAME      # every vocabulary held, directly or not, to NAME
"""

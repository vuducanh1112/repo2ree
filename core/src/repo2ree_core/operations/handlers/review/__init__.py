"""Commands that reproduce an REE inside an independent review attempt.

Each mirrors the author step it certifies, but writes only into the attempt's
parallel tree (``reviews/<review-id>/``) — the author's evidence is read-only
here, which is what makes a verdict about it worth anything.
"""

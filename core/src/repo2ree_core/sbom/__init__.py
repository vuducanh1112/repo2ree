"""Runtime-SBOM analysis: the observed side of the dependency ladder.

``cyclonedx`` adapts a CycloneDX document to observed IR rows; ``crosscheck``
merges them into the scanned inventory. Both are pure — reading the SBOM file
and rewriting the report artifact live in the handler.
"""

# Generated views of the domain model, derived from the rules that define it.
#
# The sibling of architecture.mk and journals.mk, and the third question in the
# set: those draw what the code imports and what a run did, this draws what the
# REE *is* — which evidence rests on which, and what stops being true when a
# step is re-run. Read out of domain/ree/audit.py rather than maintained here,
# so a comparison added to a step adds an edge to the picture.

.PHONY: evidence-graph ree-filmstrip ree-timeline ree-browser domain-diagrams

domain-diagrams: evidence-graph ree-filmstrip ree-timeline ree-browser

# Shared with architecture.mk, and restated with ?= so this file stands on its
# own regardless of include order. Gitignored either way: a generated view is
# not a file to review in a diff.
DIAGRAM_DIR ?= dist/diagrams
DOMAIN_DIR ?= $(DIAGRAM_DIR)/domain

# The audit rules the diagram is derived from. Named so the target can depend on
# it: the graph is a pure function of this file, so make can skip the render
# when it has not moved.
AUDIT_RULES = core/src/repo2ree_core/domain/ree/audit.py

EVIDENCE_GRAPH = $(DOMAIN_DIR)/evidence.svg

evidence-graph: $(EVIDENCE_GRAPH)

$(EVIDENCE_GRAPH): $(AUDIT_RULES) scripts/evidence_graph.py
	@mkdir -p $(DOMAIN_DIR)
	python scripts/evidence_graph.py -o $@

# The same rules, run against a real REE: the api-integration tier snapshots the
# state after each authoring act, and this draws what the audit said each time.
# Reads a capture and never produces one, like journals — so it is only as
# current as the last docker-capable run of that tier. Phony with a guard rather
# than a file rule, because a missing capture is a "run the suite" message and
# not a "no rule to make target" one.
FILMSTRIP_CAPTURE ?= test-artifacts/ree-snapshots/api-integration/test_full_authoring_pipeline.ndjson

define require_filmstrip_capture
	@test -f $(FILMSTRIP_CAPTURE) || { \
		echo "no capture at $(FILMSTRIP_CAPTURE)" >&2; \
		echo "run: make e2e-bundles && pytest api/tests/integration" >&2; \
		exit 1; \
	}
	@mkdir -p $(DOMAIN_DIR)
endef

ree-filmstrip:
	$(require_filmstrip_capture)
	python scripts/ree_filmstrip.py --frames $(FILMSTRIP_CAPTURE) -o $(DOMAIN_DIR)/ree-filmstrip.svg

# The same frames at the other altitude: every field of the aggregate that each
# act changed. HTML rather than SVG because it is text, and a browser measures
# text better than an SVG emitter's arithmetic can — the reason trace_journal.py
# gives for its own html emitter.
ree-timeline:
	$(require_filmstrip_capture)
	python scripts/ree_filmstrip.py -f timeline --frames $(FILMSTRIP_CAPTURE) -o $(DOMAIN_DIR)/ree-timeline.html

# The finished aggregate, browsable. Its one job beyond pretty-printing is
# joining the digests up: a sealed REE holds fourteen distinct ones across
# thirty-one fields, and the repeats are the evidence chain — which a general
# JSON viewer shows as thirty-one unrelated strings.
ree-browser:
	$(require_filmstrip_capture)
	python scripts/ree_filmstrip.py -f browse --frames $(FILMSTRIP_CAPTURE) -o $(DOMAIN_DIR)/ree-browser.html

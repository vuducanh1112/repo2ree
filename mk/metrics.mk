# Advisory code metrics. These reports describe the tree; unlike checks.mk,
# findings here never gate development or publishing. Tool execution errors do
# still fail so a missing report cannot be mistaken for a clean report.

METRICS_DIR ?= test-artifacts/metrics
COMPLEXITY_DIR = $(METRICS_DIR)/complexity

PYTHON_METRIC_SOURCES = \
	protocol/src \
	core/src \
	supervisor/src \
	api/src \
	executor/src \
	agent/src

TYPESCRIPT_METRIC_EXCLUDES = \
	-x '*/shell/infra/api/generated/*' \
	-x '*.test.ts' \
	-x '*.test.tsx' \
	-x '*.spec.ts' \
	-x '*.spec.tsx'

.PHONY: metrics metrics-complexity

metrics: metrics-complexity

# Keep the runtimes separate: Lizard understands both, but their constructs and
# parser implementations make a combined average misleading. `-i -1` retains
# every warning in the reports while making findings advisory. HTML is for
# browsing; CSV is the stable input for summaries and future trend reporting.
metrics-complexity:
	@mkdir -p $(COMPLEXITY_DIR)
	lizard -l python -i -1 \
		-o $(COMPLEXITY_DIR)/python.html \
		$(PYTHON_METRIC_SOURCES)
	lizard -l python -i -1 --csv \
		$(PYTHON_METRIC_SOURCES) \
		> $(COMPLEXITY_DIR)/python.csv
	lizard -l typescript -i -1 \
		$(TYPESCRIPT_METRIC_EXCLUDES) \
		-o $(COMPLEXITY_DIR)/typescript.html \
		gui/src
	lizard -l typescript -i -1 --csv \
		$(TYPESCRIPT_METRIC_EXCLUDES) \
		gui/src \
		> $(COMPLEXITY_DIR)/typescript.csv
	@echo ">> complexity reports: $(COMPLEXITY_DIR)"

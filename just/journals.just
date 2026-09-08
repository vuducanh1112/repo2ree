DEFAULT_JOURNAL_TRACE := "test-artifacts/traces/api-integration/by-test/api_tests_integration_test_api_full_pipeline.py_test_full_authoring_pipeline.ndjson"

# Journals derive one cross-component page per captured run trace. The trace is
# an integration-test artifact; absence is an error, never an empty success.

# Generate one cross-component journal page per captured workflow, replacing
# the previous complete set only after every page renders successfully.
[group('Diagrams')]
generate-journals trace=DEFAULT_JOURNAL_TRACE:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    journal_trace={{ quote(trace) }}
    test -f "$journal_trace" || {
      printf 'no capture at %s\n' "$journal_trace" >&2
      echo "run: just build-e2e-bundles && pytest api/tests/integration" >&2
      exit 1
    }
    journal_parent=$(dirname {{ quote(JOURNAL_DIR) }})
    journal_name=$(basename {{ quote(JOURNAL_DIR) }})
    mkdir -p "$journal_parent"
    pending=$(mktemp -d "$journal_parent/.${journal_name}.pending.XXXXXX")
    trap 'rm -rf "$pending"' EXIT
    python scripts/diagrams/trace_journal.py "$journal_trace" 2>/dev/null \
      | awk '$4 ~ /^run\./ { name = substr($4, 5); n = ++seen[name]; print $1, (n == 1 ? name : name "-" n) }' \
      | while read -r trace name; do
          python scripts/diagrams/trace_journal.py "$journal_trace" -f graph --trace "$trace" \
            --exclude 'docker.' --exclude 'process.exec' \
            --zone 'api=ree.,run.,POST ,GET ,PUT ,DELETE ' \
            --zone 'supervisor=workbench.' \
            --zone 'workbench=workbench.connection,workbench.request' \
            --zone 'executor cli=executor.' \
            --zone 'core=command.,script.,runnable.' \
            --title "$name — across components" \
            -o "$pending/$name.html"
        done
    journals=("$pending"/*.html)
    (( ${#journals[@]} > 0 )) || {
      echo "capture contains no run.* traces: $journal_trace" >&2
      exit 1
    }
    python scripts/replace_generated_directory.py "$pending" {{ quote(JOURNAL_DIR) }}

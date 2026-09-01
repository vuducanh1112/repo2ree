COMPLEXITY_DIR := METRICS_DIR + "/complexity"

# Generate every advisory code-metric report.
[group('Metrics')]
metrics: metrics-complexity

# Generate separate Python and TypeScript complexity reports.
[group('Metrics')]
metrics-complexity:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(COMPLEXITY_DIR) }}
    python_sources=(protocol/src core/src supervisor/src api/src executor/src agent/src)
    ts_excludes=(-x '*/shell/infra/api/generated/*' -x '*.test.ts' -x '*.test.tsx' -x '*.spec.ts' -x '*.spec.tsx')
    lizard -l python -i -1 -o {{ quote(COMPLEXITY_DIR + "/python.html") }} "${python_sources[@]}"
    lizard -l python -i -1 --csv "${python_sources[@]}" > {{ quote(COMPLEXITY_DIR + "/python.csv") }}
    lizard -l typescript -i -1 "${ts_excludes[@]}" -o {{ quote(COMPLEXITY_DIR + "/typescript.html") }} gui/src
    lizard -l typescript -i -1 --csv "${ts_excludes[@]}" gui/src > {{ quote(COMPLEXITY_DIR + "/typescript.csv") }}
    printf '>> complexity reports: %s\n' {{ quote(COMPLEXITY_DIR) }}

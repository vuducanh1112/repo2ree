const TEST_FILE_PATTERN = "[.](?:spec|test)[.](?:js|mjs|cjs|jsx|ts|mts|cts|tsx)$";
const UI_APPROVED_RAW_API_IMPORTERS = [];

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'warn',
      comment:
        "This dependency is part of a circular relationship. You might want to revise " +
        "your solution (i.e. use dependency inversion, make sure the modules have a single responsibility) ",
      from: {},
      to: {
        circular: true
      }
    },
    {
      name: 'no-orphans',
      comment:
        "This is an orphan module - it's likely not used (anymore?). Either use it or " +
        "remove it. If it's logical this module is an orphan (i.e. it's a config file), " +
        "add an exception for it in your dependency-cruiser configuration. By default " +
        "this rule does not scrutinize dot-files (e.g. .eslintrc.js), TypeScript declaration " +
        "files (.d.ts), tsconfig.json and some of the babel and webpack configs.",
      severity: 'warn',
      from: {
        orphan: true,
        pathNot: [
          '(^|/)[.][^/]+[.](?:js|cjs|mjs|ts|cts|mts|json)$',
          '[.]d[.]ts$',
          '(^|/)tsconfig[.]json$',
          '(^|/)(?:babel|webpack)[.]config[.](?:js|cjs|mjs|ts|cts|mts|json)$'
        ]
      },
      to: {},
    },
    {
      name: 'no-deprecated-core',
      comment:
        'A module depends on a node core module that has been deprecated. Find an alternative - these are ' +
        "bound to exist - node doesn't deprecate lightly.",
      severity: 'warn',
      from: {},
      to: {
        dependencyTypes: [
          'core'
        ],
        path: [
          '^v8/tools/codemap$',
          '^v8/tools/consarray$',
          '^v8/tools/csvparser$',
          '^v8/tools/logreader$',
          '^v8/tools/profile_view$',
          '^v8/tools/profile$',
          '^v8/tools/SourceMap$',
          '^v8/tools/splaytree$',
          '^v8/tools/tickprocessor-driver$',
          '^v8/tools/tickprocessor$',
          '^node-inspect/lib/_inspect$',
          '^node-inspect/lib/internal/inspect_client$',
          '^node-inspect/lib/internal/inspect_repl$',
          '^async_hooks$',
          '^punycode$',
          '^domain$',
          '^constants$',
          '^sys$',
          '^_linklist$',
          '^_stream_wrap$'
        ],
      }
    },
    {
      name: 'not-to-deprecated',
      comment:
        'This module uses a (version of an) npm module that has been deprecated. Either upgrade to a later ' +
        'version of that module, or find an alternative. Deprecated modules are a security risk.',
      severity: 'warn',
      from: {},
      to: {
        dependencyTypes: [
          'deprecated'
        ]
      }
    },
    {
      name: 'no-non-package-json',
      severity: 'error',
      comment:
        "This module depends on an npm package that isn't in the 'dependencies' section of your package.json. " +
        "That's problematic as the package either (1) won't be available on live (2 - worse) will be " +
        "available on live with an non-guaranteed version. Fix it by adding the package to the dependencies " +
        "in your package.json.",
      from: {},
      to: {
        dependencyTypes: [
          'npm-no-pkg',
          'npm-unknown'
        ]
      }
    },
    {
      name: 'not-to-unresolvable',
      comment:
        "This module depends on a module that cannot be found ('resolved to disk'). If it's an npm " +
        'module: add it to your package.json. In all other cases you likely already know what to do.',
      severity: 'error',
      from: {},
      to: {
        couldNotResolve: true
      }
    },
    {
      name: 'no-duplicate-dep-types',
      comment:
        "Likely this module depends on an external ('npm') package that occurs more than once " +
        "in your package.json i.e. bot as a devDependencies and in dependencies. This will cause " +
        "maintenance problems later on.",
      severity: 'warn',
      from: {},
      to: {
        moreThanOneDependencyType: true,
        dependencyTypesNot: ["type-only"]
      }
    },

    {
      name: 'not-to-test',
      comment:
        "This module depends on code within a folder that should only contain tests. As tests don't " +
        "implement functionality this is odd. Either you're writing a test outside the test folder " +
        "or there's something in the test folder that isn't a test.",
      severity: 'error',
      from: {
        pathNot: ['^(tests)', TEST_FILE_PATTERN]
      },
      to: {
        path: '^(tests)'
      }
    },
    {
      name: 'not-to-spec',
      comment:
        'This module depends on a spec (test) file. The responsibility of a spec file is to test code. ' +
        "If there's something in a spec that's of use to other modules, it doesn't have that single " +
        'responsibility anymore. Factor it out into (e.g.) a separate utility/ helper or a mock.',
      severity: 'error',
      from: {},
      to: {
        path: '[.](?:spec|test)[.](?:js|mjs|cjs|jsx|ts|mts|cts|tsx)$'
      }
    },
    {
      name: 'not-to-dev-dep',
      severity: 'error',
      comment:
        "This module depends on an npm package from the 'devDependencies' section of your " +
        'package.json. It looks like something that ships to production, though. To prevent problems ' +
        "with npm packages that aren't there on production declare it (only!) in the 'dependencies'" +
        'section of your package.json. If this module is development only - add it to the ' +
        'from.pathNot re of the not-to-dev-dep rule in the dependency-cruiser configuration',
      from: {
        path: '^(src)',
        pathNot: [
          '[.](?:spec|test)[.](?:js|mjs|cjs|jsx|ts|mts|cts|tsx)$',
          '[.]d[.]ts$'
        ]
      },
      to: {
        dependencyTypes: [
          'npm-dev',
        ],
        dependencyTypesNot: [
          'type-only'
        ],
        pathNot: [
          'node_modules/@types/'
        ]
      }
    },
    {
      name: 'optional-deps-used',
      severity: 'info',
      comment:
        "This module depends on an npm package that is declared as an optional dependency " +
        "in your package.json. As this makes sense in limited situations only, it's flagged here. " +
        "If you use an optional dependency here by design - add an exception to your" +
        "dependency-cruiser configuration.",
      from: {},
      to: {
        dependencyTypes: [
          'npm-optional'
        ]
      }
    },
    {
      name: 'peer-deps-used',
      comment:
        "This module depends on an npm package that is declared as a peer dependency " +
        "in your package.json. This makes sense if your package is e.g. a plugin, but in " +
        "other cases - maybe not so much. If the use of a peer dependency is intentional " +
        "add an exception to your dependency-cruiser configuration.",
      severity: 'warn',
      from: {},
      to: {
        dependencyTypes: [
          'npm-peer'
        ]
      }
    },
    {
      name: "core-no-shell",
      severity: "error",
      comment:
        "Functional core modules must not depend on imperative shell modules.",
      from: {
        path: "^src/core",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell(/|$)"
      }
    },
    {
      name: "core-no-react",
      severity: "error",
      comment:
        "Functional core modules must stay framework-free.",
      from: {
        path: "^src/core",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^(react$|react-dom$|react-router-dom$|@tanstack/react-query$)"
      }
    },
    {
      name: "core-no-browser-or-node-builtins",
      severity: "error",
      comment:
        "Functional core must not depend on Node runtime IO modules. Pass ports or plain data instead.",
      from: {
        path: "^src/core",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^(fs|node:fs|path|node:path|http|node:http|https|node:https|crypto|node:crypto|process|node:process)$"
      }
    },
    {
      name: "shell-infra-no-ui-data-or-app",
      severity: "error",
      comment:
        "Infrastructure adapters must not depend on UI, data hooks, or app bootstrap.",
      from: {
        path: "^src/shell/infra",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/(ui|data|app)(/|$)"
      }
    },
    {
      name: "shell-data-no-ui-or-app",
      severity: "error",
      comment:
        "Data/query modules must not depend on UI components or app bootstrap.",
      from: {
        path: "^src/shell/data",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/(ui|app)(/|$)"
      }
    },
    {
      name: "shell-ui-no-raw-infra",
      severity: "error",
      comment:
        "UI modules must reach server state through shell/data, not raw infrastructure clients.",
      from: {
        path: "^src/shell/ui",
        pathNot: [TEST_FILE_PATTERN, ...UI_APPROVED_RAW_API_IMPORTERS]
      },
      to: {
        path: "^src/shell/infra(/|$)"
      }
    },
    {
      name: "shell-state-no-ui",
      severity: "error",
      comment:
        "Editor state and orchestration must not depend on UI modules. UI consumes state, never owns it.",
      from: {
        path: "^src/shell/state",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/ui(/|$)"
      }
    },
    {
      name: "shell-app-imports-ui-only-from-bootstrap",
      severity: "error",
      comment:
        "App startup modules wire UI only from bootstrap; config/query modules should stay UI-free.",
      from: {
        path: "^src/shell/app/(config|query)(/|$)",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/ui(/|$)"
      }
    },
    {
      name: "shell-ui-shared-no-features",
      severity: "error",
      comment:
        "Shared UI may depend on other shared modules and theme primitives, never on a feature.",
      from: {
        path: "^src/shell/ui/shared(/|$)",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/ui/(?!shared(?:/|$)|theme(?:/|$))"
      }
    },
    {
      name: "shell-ui-theme-no-ui-dependencies",
      severity: "error",
      comment:
        "Theme primitives must not depend on shared components or feature UI.",
      from: {
        path: "^src/shell/ui/theme(/|$)",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/ui/(?!theme(?:/|$))"
      }
    },
    {
      name: "shell-ui-routes-no-feature-internals",
      severity: "error",
      comment:
        "Route composition may assemble top-level views but should not depend on feature internals. " +
        "The route constants it also needs are core data (@core/app-shell/pages), reachable from anywhere.",
      from: {
        path: "^src/shell/ui/routes",
        pathNot: TEST_FILE_PATTERN
      },
      to: {
        path: "^src/shell/ui/app-shell/(?!AppShellView(?:[.]tsx)?$)"
      }
    }
  ],
  options: {
    doNotFollow: {
      path: ['node_modules']
    },




    detectJSDocImports: true,

    detectProcessBuiltinModuleCalls: true,



    tsPreCompilationDeps: true,
    



    tsConfig: {
      fileName: 'tsconfig.json'
    },



    
    enhancedResolveOptions: {
      exportsFields: ['exports'],
      
      conditionNames: ['import', 'require', 'node', 'default', 'types'],
      
      
      
      mainFields: ["main", "types", "typings"],
      
    },

    skipAnalysisNotInRules: true,
    
    reporterOptions: {
      dot: {
        collapsePattern: 'node_modules/(?:@[^/]+/[^/]+|[^/]+)',

      },
      archi: {
        collapsePattern: '^(?:packages|src|lib(s?)|app(s?)|bin|test(s?)|spec(s?))/[^/]+|node_modules/(?:@[^/]+/[^/]+|[^/]+)',

      },
      text: {
        highlightFocused: true
      },
    }
  }
};

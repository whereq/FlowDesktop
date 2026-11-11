import js from '@eslint/js'
import globals from 'globals'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// The React Compiler rule family (eslint-plugin-react-hooks v7) flags patterns
// the app has not been migrated to yet (setState in effects, components created
// during render, ...). They are disabled so that `yarn lint` stays a usable
// gate; the classic hooks rules below stay enabled.
const reactCompilerRules = Object.fromEntries(
  Object.entries(reactHooks.configs.recommended.rules)
    .filter(([name]) => !name.startsWith('react-hooks/rules-of-hooks') && !name.startsWith('react-hooks/exhaustive-deps'))
    .map(([name]) => [name, 'off'])
)

export default [
  { ignores: ['dist', 'node_modules'] },

  // Node-side tooling config (eslint.config.js, postcss.config.js, tailwind.config.js)
  {
    files: ['*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.node },
    },
    rules: { ...js.configs.recommended.rules },
  },

  // Service worker (public/sw.js) — service-worker + browser globals.
  {
    files: ['public/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: { ...globals.serviceworker, ...globals.browser },
    },
    rules: { ...js.configs.recommended.rules },
  },

  // Application source (TypeScript / TSX).
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      // TypeScript-aware overrides: `no-undef` is redundant with tsc, and the
      // base `no-unused-vars` is superseded by the @typescript-eslint version.
      ...tsPlugin.configs['flat/eslint-recommended'].rules,
      'no-unused-vars': 'off',
      ...tsPlugin.configs.recommended.rules,
      // Classic React hooks rules stay on ...
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      ...reactCompilerRules,
      // Fast-refresh export hints are advisory only.
      'react-refresh/only-export-components': 'off',
    },
  },
]

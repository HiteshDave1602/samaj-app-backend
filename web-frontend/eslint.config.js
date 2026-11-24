import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // The browser's "localhost says" boxes: use useToast() and useConfirm() (shared/api.js) instead.
      // A local `const confirm = useConfirm()` shadows the global, so only real browser calls are flagged.
      'no-restricted-globals': ['error',
        ...['alert', 'confirm', 'prompt'].map((name) => ({ name, message: 'Use useConfirm() / useToast() from shared/api.js' }))],
      'no-restricted-properties': ['error',
        ...['alert', 'confirm', 'prompt'].map((property) => ({ object: 'window', property, message: 'Use useConfirm() / useToast() from shared/api.js' }))],
    },
  },
])

import { defineConfig } from 'vitest/config';
import path from 'path';

const config = defineConfig({
  resolve: {
    alias: {
      // Ensure tree-sitter-wasms resolves correctly in vitest
      'tree-sitter-wasms': path.resolve(__dirname, 'node_modules/tree-sitter-wasms/out'),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: [
      'engine/tests/unit/**/*.test.ts',
      'engine/tests/integration/**/*.test.ts',
      'engine/tests/benchmarks/**/*.test.ts',
    ],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.git/**',
      '**/coverage/**',
      '.anchor/inbox/**',
    ],
    unstubAllExports: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts', 'engine/tests/**/*.test.ts'],
      exclude: [
        'src/types/**/*.ts',
        'src/index.ts',
        '**/*.d.ts',
      ],
    },
    testTimeout: 30000,
    hookTimeout: 10000,
    reporters: ['verbose'],
    define: {
      __DEV__: JSON.stringify(process.env.NODE_ENV === 'development'),
      __TEST__: JSON.stringify(true),
    },
    setupFiles: ['engine/tests/setup.ts'],
  },
});

export default config;

// Engine setup file (separate)
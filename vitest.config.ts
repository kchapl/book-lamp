import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./vitest.setup.ts'],
        include: ['src/react/**/*.test.ts', 'src/react/**/*.test.tsx'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
            include: ['src/react/**/*.ts', 'src/react/**/*.tsx'],
            exclude: ['src/react/**/*.test.ts', 'src/react/**/*.test.tsx']
        }
    }
});

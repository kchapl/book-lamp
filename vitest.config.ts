import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./vitest.setup.ts'],
        include: ['src/ts/**/*.test.ts', 'src/react/**/*.test.ts', 'src/react/**/*.test.tsx'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
            include: ['src/ts/**/*.ts'],
            exclude: ['src/ts/**/*.test.ts']
        }
    }
});

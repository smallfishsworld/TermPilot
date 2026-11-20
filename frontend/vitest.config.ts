import { defineConfig } from 'vitest/config'

// Unit tests cover the framework-free helpers in app/utils.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.spec.ts'],
  },
})

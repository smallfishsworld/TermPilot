import tailwindcss from '@tailwindcss/vite'

// The client is a single-page app: every view needs the student's token, which lives in the browser.
export default defineNuxtConfig({
  compatibilityDate: '2026-11-01',
  ssr: false,
  devtools: { enabled: false },
  modules: ['@pinia/nuxt'],
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      title: 'TermPilot',
      htmlAttrs: { lang: 'en' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'Timetable, deadlines, grades and mail for your semester, plus an assistant that asks before it acts.' },
        { name: 'theme-color', content: '#0f766e' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },
  runtimeConfig: {
    public: {
      // Override with NUXT_PUBLIC_API_BASE, e.g. https://termpilot.example.edu
      apiBase: 'http://localhost:8000',
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
  typescript: {
    strict: true,
  },
})

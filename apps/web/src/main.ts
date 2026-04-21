import * as Sentry from '@sentry/vue'
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import './styles.css'
import './theme.scss'

import App from './App.vue'
import router from './router'

const app = createApp(App)

function envBoolean(value: string | undefined): boolean {
  return value === 'true'
}

function envNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    sendDefaultPii: envBoolean(import.meta.env.VITE_SENTRY_SEND_DEFAULT_PII),
    integrations: [Sentry.browserTracingIntegration({ router }), Sentry.replayIntegration()],
    tracesSampleRate: envNumber(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE, 0),
    tracePropagationTargets: ['localhost', /^https:\/\/baboom\.com\.br\/api/],
    replaysSessionSampleRate: envNumber(import.meta.env.VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE, 0),
    replaysOnErrorSampleRate: envNumber(
      import.meta.env.VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE,
      1,
    ),
    enableLogs: envBoolean(import.meta.env.VITE_SENTRY_ENABLE_LOGS),
  })
}

app.use(createPinia())
app.use(router)

app.mount('#app')

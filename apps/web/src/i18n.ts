import { createI18n } from 'vue-i18n'
import enUS from '@/locales/en-US.json'
import ptBR from '@/locales/pt-BR.json'

type MessageSchema = typeof enUS

declare module 'vue-i18n' {
  export interface DefineLocaleMessage {
    common: MessageSchema['common']
    header: MessageSchema['header']
    catalog: MessageSchema['catalog']
    payment: MessageSchema['payment']
    alerts: MessageSchema['alerts']
  }
}

export const i18n = createI18n({
  legacy: false,
  locale: 'pt-BR',
  fallbackLocale: 'en-US',
  messages: { 'pt-BR': ptBR, 'en-US': enUS },
})

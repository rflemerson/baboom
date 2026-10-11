import { describe, expect, it } from 'vitest'
import messages from './locales/en-US.json'
import ptBR from './locales/pt-BR.json'
import { i18n } from './i18n'

const sources = import.meta.glob('./**/*.{vue,ts}', {
  query: '?raw',
  import: 'default',
  eager: true,
})
function leaves(value: unknown, prefix = ''): Array<{ key: string; message: string }> {
  if (typeof value === 'string') return [{ key: prefix, message: value }]
  if (!value || typeof value !== 'object') throw new Error(`Invalid message: ${prefix}`)
  return Object.entries(value).flatMap(([key, child]) =>
    leaves(child, prefix ? `${prefix}.${key}` : key),
  )
}

describe('interface translations', () => {
  it('resolves every literal translation key from the English base', () => {
    const base = leaves(messages)
    const keys = new Set(base.map((entry) => entry.key))
    const unresolved: string[] = []
    for (const [path, source] of Object.entries(sources)) {
      if (path.endsWith('.spec.ts') || typeof source !== 'string') continue
      for (const match of source.matchAll(/\bt\(['"]([^'"]+)['"]/g)) {
        if (!keys.has(match[1] ?? '')) unresolved.push(`${path}: ${match[1]}`)
      }
    }
    expect(unresolved).toEqual([])
    expect(base.filter((entry) => !entry.message.trim())).toEqual([])
  })
  it('speaks Brazilian Portuguese by default, falling back to English', () => {
    expect(i18n.global.locale.value).toBe('pt-BR')
    expect(i18n.global.fallbackLocale.value).toBe('en-US')
    expect(i18n.global.t('catalog.column.pricePerActive')).toBe('Preço/100 g')
    expect(i18n.global.t('alerts.emailPlaceholder')).toBe('seu@email.com')
  })

  it('translates every English message to Portuguese', () => {
    const keys = (value: unknown) => leaves(value).map((entry) => entry.key)
    expect(keys(ptBR)).toEqual(keys(messages))
  })
})

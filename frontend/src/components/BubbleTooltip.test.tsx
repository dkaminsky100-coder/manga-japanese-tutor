// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { DictEntry, TextBlock, WordToken } from '../api/client'
import BubbleTooltip from './BubbleTooltip'

const entry = (id: number, kanji: string[], kana: string[], glosses: string[], pos = ['Ichidan verb']): DictEntry => ({
  id, common: id === 1, kanji, kana, more_senses: 0, senses: [{ pos, glosses, misc: [] }],
})

const taberu: WordToken = {
  surface: '食べ', reading: 'たべ', dictionary_form: '食べる', pos: '動詞', pos_label: 'verb', pos_detail: '一般',
  conj_type: '下一段-バ行', conj_form: '連用形-一般',
  ruby: [{ text: '食', ruby: 'た' }, { text: 'べ', ruby: null }],
  entries: [entry(1, ['食べる'], ['たべる'], ['to eat']), entry(2, ['喰べる'], ['たべる'], ['to eat (variant)'])],
  parts: [],
}
const bang: WordToken = {
  surface: '！', reading: '！', dictionary_form: '!', pos: '補助記号', pos_label: 'symbol', pos_detail: '句点',
  conj_type: '', conj_form: '', ruby: [{ text: '！', ruby: null }], entries: [], parts: [],
}
const unknown: WordToken = { ...taberu, surface: 'キョロ', pos_label: 'noun', dictionary_form: 'キョロ', conj_form: '',
  ruby: [{ text: 'キョロ', ruby: null }], entries: [] }

const block = (tokens: WordToken[], compounds: TextBlock['compounds'] = []): TextBlock => ({
  id: 1, bbox: [0, 0, 1, 1], vertical: true, conf: 1, text: tokens.map((t) => t.surface).join(''), tokens, compounds,
})

afterEach(cleanup)

describe('BubbleTooltip', () => {
  it('renders furigana as <ruby> over kanji only', () => {
    const { container } = render(<BubbleTooltip block={block([taberu])} pinned={false} />)
    const ruby = container.querySelector('.tooltip-text ruby')!
    expect(ruby.textContent).toContain('食')
    expect(ruby.querySelector('rt')!.textContent).toBe('た')
    expect(container.querySelectorAll('.tooltip-text rt')).toHaveLength(1) // べ has no ruby
  })

  it('lists each word with its part of speech, base form, inflection and definition', () => {
    const { container } = render(<BubbleTooltip block={block([taberu])} pinned={false} />)
    const word = container.querySelector('li.word') as HTMLElement
    expect(within(word).getByText('verb')).toBeTruthy()
    expect(within(word).getByText('← 食べる')).toBeTruthy()
    expect(within(word).getByText('連用形-一般')).toBeTruthy()
    expect(within(word).getByText(/to eat$/)).toBeTruthy()
  })

  it('tucks additional dictionary entries into a collapsed section', () => {
    const { container } = render(<BubbleTooltip block={block([taberu])} pinned={false} />)
    const details = container.querySelector('details.other-entries')!
    expect(details.querySelector('summary')!.textContent).toBe('1 other entry')
    expect(details.hasAttribute('open')).toBe(false)
  })

  it('skips punctuation in the word list but keeps it in the sentence', () => {
    const { container } = render(<BubbleTooltip block={block([taberu, bang])} pinned={false} />)
    expect(container.querySelectorAll('li.word')).toHaveLength(1)
    expect(container.querySelector('.tooltip-text')!.textContent).toContain('！')
  })

  it('says so when a word has no dictionary entry', () => {
    render(<BubbleTooltip block={block([unknown])} pinned={false} />)
    expect(screen.getByText('No dictionary entry found.')).toBeTruthy()
  })

  it('shows phrases when compounds were found', () => {
    const phrase = { start: 0, end: 3, text: '気をつける', entries: [entry(9, ['気をつける'], ['きをつける'], ['to be careful'], ['Expression'])] }
    render(<BubbleTooltip block={block([taberu], [phrase])} pinned={false} />)
    expect(screen.getByText('Phrases')).toBeTruthy()
    expect(screen.getByText('気をつける')).toBeTruthy()
  })

  it('falls back to the raw OCR text when there are no tokens', () => {
    const b = { ...block([]), text: 'こんにちは' }
    render(<BubbleTooltip block={b} pinned />)
    expect(screen.getByText('こんにちは')).toBeTruthy()
    expect(screen.getByText(/Pinned/)).toBeTruthy()
  })
})

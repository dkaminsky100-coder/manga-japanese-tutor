// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { isTypingTarget } from './keys'

const el = (tag: string, attrs: Record<string, string> = {}) => {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v)
  return e
}

describe('isTypingTarget', () => {
  it('is true for text fields', () => {
    expect(isTypingTarget(el('textarea'))).toBe(true)
    expect(isTypingTarget(el('input'))).toBe(true) // type defaults to text
    expect(isTypingTarget(el('input', { type: 'search' }))).toBe(true)
    expect(isTypingTarget(el('div', { contenteditable: 'true' }))).toBe(true)
  })

  it('is false for controls that are not text entry, so arrow-key page turning keeps working', () => {
    expect(isTypingTarget(el('input', { type: 'checkbox' }))).toBe(false)
    expect(isTypingTarget(el('input', { type: 'radio' }))).toBe(false)
    expect(isTypingTarget(el('button'))).toBe(false)
    expect(isTypingTarget(el('div'))).toBe(false)
    expect(isTypingTarget(document.body)).toBe(false)
  })

  it('is false when there is no element target', () => {
    expect(isTypingTarget(null)).toBe(false)
    expect(isTypingTarget(window)).toBe(false)
  })
})

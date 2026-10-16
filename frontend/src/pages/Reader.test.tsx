// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Reader from './Reader'

vi.mock('../api/client', () => ({
  getChapter: vi.fn().mockResolvedValue({
    id: 1,
    title: 'Test',
    pages: [
      { id: 10, idx: 0, width: 100, height: 100 },
      { id: 11, idx: 1, width: 100, height: 100 },
      { id: 12, idx: 2, width: 100, height: 100 },
    ],
  }),
}))
vi.mock('../components/PageView', () => ({ default: ({ page }: { page: { id: number } }) => <div data-testid="page">{page.id}</div> }))

afterEach(cleanup)

async function renderReader() {
  render(
    <MemoryRouter initialEntries={['/read/1']}>
      <Routes>
        <Route path="/read/:chapterId" element={<Reader />} />
      </Routes>
    </MemoryRouter>,
  )
  await screen.findByTestId('page')
}
const shownPage = () => screen.getByTestId('page').textContent

describe('Reader keyboard navigation', () => {
  it('turns pages right-to-left: ArrowLeft goes on, ArrowRight goes back', async () => {
    await renderReader()
    expect(shownPage()).toBe('10')
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(shownPage()).toBe('11')
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(shownPage()).toBe('10')
  })

  it('does not turn the page while typing in a text field (arrows move the caret)', async () => {
    await renderReader()
    const textarea = document.body.appendChild(document.createElement('textarea'))
    fireEvent.keyDown(textarea, { key: 'ArrowLeft' })
    fireEvent.keyDown(textarea, { key: 'ArrowLeft' })
    expect(shownPage()).toBe('10')
    textarea.remove()
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(shownPage()).toBe('11') // and it works again once the field is gone
  })

  it('still turns pages when the Boxes checkbox has focus', async () => {
    await renderReader()
    const checkbox = screen.getByRole('checkbox')
    checkbox.focus()
    fireEvent.keyDown(checkbox, { key: 'ArrowLeft' })
    expect(shownPage()).toBe('11')
  })

  it('stops at the first and last page', async () => {
    await renderReader()
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(shownPage()).toBe('10')
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(shownPage()).toBe('12')
  })
})

// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import type { TextBlock } from '../api/client'
import PageView from './PageView'

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  getAnalysis: vi.fn(),
  editBlock: vi.fn(),
  revertBlock: vi.fn(),
}))
const getAnalysis = vi.mocked(client.getAnalysis)
const editBlock = vi.mocked(client.editBlock)
const revertBlock = vi.mocked(client.revertBlock)

const block = (id: number, text: string, extra: Partial<TextBlock> = {}): TextBlock => ({
  id, bbox: [100 * id, 100, 100 * id + 50, 200], vertical: true, conf: 1, text, ocr_text: text, edited: false,
  tokens: [], compounds: [], grammar: [], ...extra,
})
const analysis = (blocks: TextBlock[]) => ({ status: 'done' as const, error: null, upscaled: false, detect_ms: 1, ocr_ms: 1, blocks })
const page = { id: 1, idx: 0, width: 1000, height: 1500 }

beforeEach(() => {
  getAnalysis.mockReset()
  editBlock.mockReset()
  revertBlock.mockReset()
})
afterEach(cleanup)

async function renderPage(blocks: TextBlock[]) {
  getAnalysis.mockResolvedValue(analysis(blocks))
  const user = userEvent.setup()
  const { container } = render(<PageView page={page} showBoxes={false} />)
  await waitFor(() => expect(container.querySelectorAll('.block-box')).toHaveLength(blocks.length))
  return { user, boxes: Array.from(container.querySelectorAll<HTMLElement>('.block-box')), container }
}

describe('PageView', () => {
  it('shows the corrected text in the tooltip after saving, and leaves the other blocks alone', async () => {
    const { user, boxes } = await renderPage([block(1, 'こんにちは'), block(2, 'さようなら')])
    editBlock.mockResolvedValue(block(1, '食べた', { ocr_text: 'こんにちは', edited: true }))

    await user.click(boxes[0])
    await user.click(await screen.findByRole('button', { name: 'Edit text' }))
    const box = screen.getByLabelText('Corrected text')
    await user.clear(box)
    await user.type(box, '食べた')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(document.querySelector('.tooltip-text')?.textContent).toBe('食べた'))
    expect(screen.getByText('edited')).toBeTruthy()
    expect(screen.getByText('OCR read: こんにちは')).toBeTruthy()
    expect(editBlock).toHaveBeenCalledWith(1, '食べた')
    expect(getAnalysis).toHaveBeenCalledTimes(1) // swapped in place, no refetch of the page

    // the second bubble still shows its own text
    await user.keyboard('{Escape}') // close the first tooltip
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
    await user.click(boxes[1])
    await waitFor(() => expect(document.querySelector('.tooltip-text')?.textContent).toBe('さようなら'))
  })

  it('goes back to the OCR text after Reset', async () => {
    const { user, boxes } = await renderPage([block(1, '食べた', { ocr_text: 'こんにちは', edited: true })])
    revertBlock.mockResolvedValue(block(1, 'こんにちは'))
    await user.click(boxes[0])
    await user.click(await screen.findByRole('button', { name: 'Reset to OCR' }))
    await waitFor(() => expect(document.querySelector('.tooltip-text')?.textContent).toBe('こんにちは'))
    expect(screen.queryByText('edited')).toBeNull()
  })

  it('lists the corrected text in the Boxes debug list', async () => {
    getAnalysis.mockResolvedValue(analysis([block(1, '食べた', { ocr_text: 'こんにちは', edited: true })]))
    render(<PageView page={page} showBoxes />)
    expect((await screen.findByRole('listitem')).textContent).toBe('食べた')
  })
})

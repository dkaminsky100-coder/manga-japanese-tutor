// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import Bubble from './Bubble'

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  translateBlock: vi.fn(),
  editBlock: vi.fn(),
  revertBlock: vi.fn(),
}))
const translateBlock = vi.mocked(client.translateBlock)
const editBlock = vi.mocked(client.editBlock)
const revertBlock = vi.mocked(client.revertBlock)
const result = (translation: string) => ({ translation, model: 'test', cached: false })

const block = { id: 1, bbox: [10, 20, 40, 90] as [number, number, number, number], vertical: true, conf: 0.9, text: 'こんにちは', tokens: [], compounds: [], grammar: [], ocr_text: 'こんにちは', edited: false }
const rect = { left: 10, top: 10, width: 20, height: 20 }

function setup(over: Partial<typeof block> = {}, onChange = vi.fn()) {
  const user = userEvent.setup()
  const b = { ...block, ...over }
  const utils = render(
    <div>
      <Bubble block={b} rect={rect} label={null} onChange={onChange} />
      <button>elsewhere</button>
    </div>,
  )
  const box = utils.container.querySelector('.block-box') as HTMLElement
  return { user, box, onChange, utils, b }
}

beforeEach(() => {
  translateBlock.mockReset()
  editBlock.mockReset()
  revertBlock.mockReset()
})
afterEach(cleanup)

describe('Bubble', () => {
  it('shows no tooltip until hovered', () => {
    setup()
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('shows the OCR text on hover and hides it when the pointer leaves', async () => {
    const { user, box } = setup()
    await user.hover(box)
    expect(await screen.findByText('こんにちは')).toBeTruthy()
    expect(screen.getByText('Click to pin')).toBeTruthy()

    await user.unhover(box)
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  })

  it('stays open after the pointer leaves once pinned by a click', async () => {
    const { user, box } = setup()
    await user.click(box)
    expect(await screen.findByText(/Pinned/)).toBeTruthy()

    await user.unhover(box)
    await new Promise((r) => setTimeout(r, 300)) // longer than the hover close delay
    expect(screen.queryByRole('tooltip')).not.toBeNull()
  })

  it('closes a pinned tooltip on Escape', async () => {
    const { user, box } = setup()
    await user.click(box)
    await screen.findByText(/Pinned/)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  })

  it('closes a pinned tooltip when clicking elsewhere', async () => {
    const { user, box } = setup()
    await user.click(box)
    await screen.findByText(/Pinned/)
    await user.click(screen.getByText('elsewhere'))
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  })

  it('unpins when the bubble is clicked again', async () => {
    const { user, box } = setup()
    await user.click(box)
    await screen.findByText(/Pinned/)
    await user.click(box)
    await user.unhover(box)
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  })

  describe('translation', () => {
    it('translates on click and labels the result as rough', async () => {
      let resolve!: (v: ReturnType<typeof result>) => void
      translateBlock.mockReturnValue(new Promise((r) => (resolve = r)))
      const { user, box } = setup()
      await user.click(box) // pin
      await user.click(await screen.findByRole('button', { name: 'Translate' }))
      expect(await screen.findByText('Translating…')).toBeTruthy()
      expect(translateBlock).toHaveBeenCalledWith(1)

      resolve(result("I can't help it."))
      expect(await screen.findByText("I can't help it.")).toBeTruthy()
      expect(screen.getByText(/Rough machine translation/)).toBeTruthy()
      expect(screen.queryByRole('button', { name: 'Translate' })).toBeNull()
    })

    it('keeps the translation when the tooltip closes and reopens, without asking again', async () => {
      translateBlock.mockResolvedValue(result('Hello.'))
      const { user, box } = setup()
      await user.click(box)
      await user.click(await screen.findByRole('button', { name: 'Translate' }))
      await screen.findByText('Hello.')

      await user.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
      await user.click(box)
      expect(await screen.findByText('Hello.')).toBeTruthy()
      expect(translateBlock).toHaveBeenCalledTimes(1)
    })

    it('shows an error and lets you retry', async () => {
      translateBlock.mockRejectedValueOnce(new Error('Translation model unavailable')).mockResolvedValueOnce(result('Fine.'))
      const { user, box } = setup()
      await user.click(box)
      await user.click(await screen.findByRole('button', { name: 'Translate' }))
      expect(await screen.findByText(/Translation model unavailable/)).toBeTruthy()

      await user.click(screen.getByRole('button', { name: 'Try again' }))
      expect(await screen.findByText('Fine.')).toBeTruthy()
      expect(translateBlock).toHaveBeenCalledTimes(2)
    })

    it('does not translate until asked', async () => {
      const { user, box } = setup()
      await user.hover(box)
      await screen.findByRole('tooltip')
      expect(translateBlock).not.toHaveBeenCalled()
    })
  })

  describe('correcting the text', () => {
    const corrected = { ...block, text: '食べた', edited: true }

    async function startEditing(over: Partial<typeof block> = {}, onChange = vi.fn()) {
      const ctx = setup(over, onChange)
      await ctx.user.click(ctx.box) // pin
      await ctx.user.click(await screen.findByRole('button', { name: 'Edit text' }))
      return { ...ctx, textarea: screen.getByLabelText('Corrected text') as HTMLTextAreaElement }
    }

    it('saves a correction through the API and hands the updated block to the page', async () => {
      editBlock.mockResolvedValue(corrected)
      const { user, textarea, onChange } = await startEditing()
      expect(textarea.value).toBe('こんにちは')
      await user.clear(textarea)
      await user.type(textarea, '食べた')
      await user.click(screen.getByRole('button', { name: 'Save' }))

      expect(editBlock).toHaveBeenCalledWith(1, '食べた')
      await waitFor(() => expect(onChange).toHaveBeenCalledWith(corrected))
      await waitFor(() => expect(screen.queryByLabelText('Corrected text')).toBeNull()) // back to reading
    })

    it('does not call the API when nothing changed', async () => {
      const { user } = await startEditing()
      await user.click(screen.getByRole('button', { name: 'Save' }))
      expect(editBlock).not.toHaveBeenCalled()
      expect(screen.queryByLabelText('Corrected text')).toBeNull()
    })

    it('keeps the editor open and shows the error when saving fails', async () => {
      editBlock.mockRejectedValue(new Error('Text is too long'))
      const { user, textarea, onChange } = await startEditing()
      await user.type(textarea, 'あ')
      await user.click(screen.getByRole('button', { name: 'Save' }))
      expect(await screen.findByText('Text is too long')).toBeTruthy()
      expect(onChange).not.toHaveBeenCalled()
      expect((screen.getByLabelText('Corrected text') as HTMLTextAreaElement).value).toBe('こんにちはあ') // typing kept
    })

    it('keeps the tooltip open while editing when the pointer leaves or you click elsewhere', async () => {
      const { user, box, textarea } = await startEditing()
      await user.type(textarea, 'あ')
      await user.unhover(box)
      await user.click(screen.getByText('elsewhere'))
      await new Promise((r) => setTimeout(r, 300))
      expect(screen.queryByRole('tooltip')).not.toBeNull()
      expect((screen.getByLabelText('Corrected text') as HTMLTextAreaElement).value).toBe('こんにちはあ')
    })

    it('Escape cancels the edit but leaves the tooltip open', async () => {
      const { user, textarea } = await startEditing()
      await user.type(textarea, 'あ')
      await user.keyboard('{Escape}')
      expect(screen.queryByLabelText('Corrected text')).toBeNull()
      expect(screen.queryByRole('tooltip')).not.toBeNull()
      expect(editBlock).not.toHaveBeenCalled()
      // ...and a second Escape now closes the tooltip as usual
      await user.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
    })

    it('clicking the bubble while editing does not close the editor', async () => {
      const { user, box } = await startEditing()
      await user.click(box)
      expect(screen.queryByLabelText('Corrected text')).not.toBeNull()
    })

    it('resets a corrected block to the OCR text', async () => {
      revertBlock.mockResolvedValue({ ...block })
      const { user, box, onChange } = setup({ text: '食べた', ocr_text: 'こんにちは', edited: true })
      await user.click(box)
      await user.click(await screen.findByRole('button', { name: 'Reset to OCR' }))
      expect(revertBlock).toHaveBeenCalledWith(1)
      await waitFor(() => expect(onChange).toHaveBeenCalledWith({ ...block }))
    })

    it('drops the translation of the old text after a correction, and restores it if the correction is undone', async () => {
      translateBlock.mockResolvedValue(result('Hello.'))
      const { user, box, utils, b } = setup()
      await user.click(box)
      await user.click(await screen.findByRole('button', { name: 'Translate' }))
      await screen.findByText('Hello.')

      const rerenderWith = (text: string) =>
        utils.rerender(
          <div>
            <Bubble block={{ ...b, text }} rect={rect} label={null} onChange={() => {}} />
            <button>elsewhere</button>
          </div>,
        )
      rerenderWith('食べた') // the page now shows the corrected block
      expect(screen.queryByText('Hello.')).toBeNull()
      expect(screen.getByRole('button', { name: 'Translate' })).toBeTruthy()

      rerenderWith('こんにちは') // correction undone
      expect(screen.getByText('Hello.')).toBeTruthy()
      expect(translateBlock).toHaveBeenCalledTimes(1)
    })

    it('ignores a translation that finishes after the text was corrected', async () => {
      let resolve!: (v: ReturnType<typeof result>) => void
      translateBlock.mockReturnValue(new Promise((r) => (resolve = r)))
      const { user, box, utils, b } = setup()
      await user.click(box)
      await user.click(await screen.findByRole('button', { name: 'Translate' }))
      utils.rerender(
        <div>
          <Bubble block={{ ...b, text: '食べた' }} rect={rect} label={null} onChange={() => {}} />
          <button>elsewhere</button>
        </div>,
      )
      resolve(result('Stale translation of the old text'))
      await new Promise((r) => setTimeout(r, 50))
      expect(screen.queryByText('Stale translation of the old text')).toBeNull()
      expect(screen.getByRole('button', { name: 'Translate' })).toBeTruthy()
    })
  })
})

// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import Bubble from './Bubble'

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  translateBlock: vi.fn(),
}))
const translateBlock = vi.mocked(client.translateBlock)
const result = (translation: string) => ({ translation, model: 'test', cached: false })

const block = { id: 1, bbox: [10, 20, 40, 90] as [number, number, number, number], vertical: true, conf: 0.9, text: 'こんにちは', tokens: [], compounds: [] }
const rect = { left: 10, top: 10, width: 20, height: 20 }

function setup() {
  const user = userEvent.setup()
  const utils = render(
    <div>
      <Bubble block={block} rect={rect} label={null} />
      <button>elsewhere</button>
    </div>,
  )
  const box = utils.container.querySelector('.block-box') as HTMLElement
  return { user, box }
}

beforeEach(() => translateBlock.mockReset())
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
})

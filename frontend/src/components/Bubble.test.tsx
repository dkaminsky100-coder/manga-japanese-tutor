// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import Bubble from './Bubble'

const block = { id: 1, bbox: [10, 20, 40, 90] as [number, number, number, number], vertical: true, conf: 0.9, text: 'こんにちは' }
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
})

import { describe, expect, it } from 'vitest'
import { fitToAvailable, MIN_TOOLTIP_HEIGHT, MIN_TOOLTIP_WIDTH } from './layout'

describe('fitToAvailable', () => {
  it('limits the tooltip to the available space', () => {
    expect(fitToAvailable(500, 300)).toEqual({ maxWidth: '500px', maxHeight: '300px' })
  })

  it('rounds down fractional space so it never overflows by a pixel', () => {
    expect(fitToAvailable(400.9, 250.7)).toEqual({ maxWidth: '400px', maxHeight: '250px' })
  })

  it('never shrinks below a readable minimum, even with no room or negative room', () => {
    expect(fitToAvailable(50, 10)).toEqual({ maxWidth: `${MIN_TOOLTIP_WIDTH}px`, maxHeight: `${MIN_TOOLTIP_HEIGHT}px` })
    expect(fitToAvailable(-30, -5).maxHeight).toBe(`${MIN_TOOLTIP_HEIGHT}px`)
  })
})

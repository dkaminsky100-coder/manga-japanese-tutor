import { describe, expect, it } from 'vitest'
import { bboxToPercent } from './coords'

describe('bboxToPercent', () => {
  it('maps a box to percentages of the page', () => {
    expect(bboxToPercent([100, 200, 300, 600], 1000, 2000)).toEqual({
      left: 10,
      top: 10,
      width: 20,
      height: 20,
    })
  })

  it('covers the whole page for a full-size box', () => {
    expect(bboxToPercent([0, 0, 705, 917], 705, 917)).toEqual({ left: 0, top: 0, width: 100, height: 100 })
  })

  it('is independent of the rendered size (only natural size matters)', () => {
    const a = bboxToPercent([141, 183, 282, 367], 705, 917)
    expect(a.left).toBeCloseTo(20, 5)
    expect(a.top).toBeCloseTo(19.956, 2)
  })
})

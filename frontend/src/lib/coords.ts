/** Box as [x1, y1, x2, y2] in the page image's natural pixel coordinates. */
export type BBox = [number, number, number, number]

export interface PercentRect {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Convert a natural-pixel box to percentages of the page size. Absolutely positioned
 * overlays using these values track the <img> at any rendered size, zoom or fit mode
 * without recomputing anything in JS.
 */
export function bboxToPercent(bbox: BBox, pageWidth: number, pageHeight: number): PercentRect {
  const [x1, y1, x2, y2] = bbox
  return {
    left: (x1 / pageWidth) * 100,
    top: (y1 / pageHeight) * 100,
    width: ((x2 - x1) / pageWidth) * 100,
    height: ((y2 - y1) / pageHeight) * 100,
  }
}

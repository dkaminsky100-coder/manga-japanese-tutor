/** Smallest the tooltip may be squeezed to; below this it is better to scroll the page than to show a sliver. */
export const MIN_TOOLTIP_HEIGHT = 120
export const MIN_TOOLTIP_WIDTH = 200

/** Space kept clear at the viewport edges; the top is larger to clear the sticky reader header. */
export const VIEWPORT_PADDING = { top: 56, right: 8, bottom: 8, left: 8 }

/**
 * Size limits for a floating tooltip given the room Floating UI says is available on its side
 * of the bubble. The tooltip scrolls internally (overflow-y: auto) when its content is taller.
 */
export function fitToAvailable(availableWidth: number, availableHeight: number) {
  return {
    maxWidth: `${Math.max(MIN_TOOLTIP_WIDTH, Math.floor(availableWidth))}px`,
    maxHeight: `${Math.max(MIN_TOOLTIP_HEIGHT, Math.floor(availableHeight))}px`,
  }
}
